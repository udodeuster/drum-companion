from __future__ import annotations

import argparse
import sys
from queue import Empty

from drum_companion.audio.analysis import AudioAnalyzer, estimate_performance_context
from drum_companion.audio.groove import GrooveFollower, build_pattern, generate_accompaniment
from drum_companion.audio.input import CaptureError, MicrophoneCapture, list_input_devices
from drum_companion.audio.output import (
    OutputError,
    PlaybackCoordinator,
    SampleOutput,
    list_output_devices,
)
from drum_companion.ui import GrooveDashboard, InteractionPreset


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Drum companion scaffold for solo guitar and voice performances.")
    parser.add_argument("--tempo", type=float, default=92.0, help="Detected lead tempo in BPM.")
    parser.add_argument("--voice-energy", type=float, default=0.7, help="Voice intensity from 0.0 to 1.0.")
    parser.add_argument("--guitar-energy", type=float, default=0.8, help="Guitar intensity from 0.0 to 1.0.")
    parser.add_argument("--phrase", type=str, default="verse", help="Lead phrase context e.g. verse or chorus.")
    parser.add_argument("--style", type=str, default="rock", help="Groove style: rock, folk, or indie.")
    parser.add_argument("--feel", type=str, default="tight", help="Groove feel: tight or relaxed.")
    parser.add_argument("--intensity", type=float, default=0.8, help="Accompaniment energy from 0.0 to 1.0.")
    parser.add_argument("--interactive", action="store_true", help="Enter a small terminal interaction loop for tuning the groove.")
    parser.add_argument("--list-inputs", action="store_true", help="List available microphone input devices.")
    parser.add_argument("--list-outputs", action="store_true", help="List available drum playback devices.")
    parser.add_argument("--live", action="store_true", help="Start live microphone analysis; press Ctrl+C to stop.")
    parser.add_argument("--play-drums", action="store_true", help="Render the groove to an audio output while using --live.")
    parser.add_argument("--output-device", type=int, help="Output device index shown by --list-outputs.")
    parser.add_argument("--master-level", type=float, default=0.75, help="Drum output level from 0.0 to 1.0.")
    parser.add_argument("--device", type=int, help="Input device index shown by --list-inputs.")
    return parser.parse_args(argv)


def run_interactive() -> int:
    while True:
        phrase = input("Phrase (verse/chorus/bridge) [verse]: ") or "verse"
        style = input("Style (rock/folk/indie) [rock]: ") or "rock"
        feel = input("Feel (tight/relaxed) [tight]: ") or "tight"
        intensity = input("Intensity (0.0-1.0) [0.8]: ") or "0.8"

        preset = InteractionPreset.from_input(phrase, style, feel, intensity)
        dashboard = GrooveDashboard(tempo=92.0, **preset.__dict__)
        print()
        print(dashboard.render())

        again = input("Adjust again? [y/N]: ").strip().lower()
        if again not in {"y", "yes"}:
            break
    return 0


def apply_playback_key(key: str, output: SampleOutput) -> bool:
    """Apply one live console key; return True when playback should stop."""
    normalized = key.lower()
    if normalized == "m":
        output.set_muted(not output.is_muted)
        print("\nDrum output muted." if output.is_muted else "\nDrum output unmuted.")
    elif normalized in {"+", "="}:
        output.set_master_level(min(1.0, output.master_level + 0.1))
        print(f"\nDrum output level: {output.master_level:.1f}")
    elif normalized == "-":
        output.set_master_level(max(0.0, output.master_level - 0.1))
        print(f"\nDrum output level: {output.master_level:.1f}")
    elif normalized == "q":
        return True
    return False


def poll_playback_controls(output: SampleOutput) -> bool:
    try:
        import msvcrt
    except ImportError:
        return False

    stop_requested = False
    while msvcrt.kbhit():
        key = msvcrt.getwch()
        if key in {"\x00", "\xe0"}:
            msvcrt.getwch()
            continue
        stop_requested = apply_playback_key(key, output) or stop_requested
    return stop_requested


def run_live(
    device: int | None = None,
    style: str = "rock",
    feel: str = "tight",
    intensity: float = 0.8,
    phrase: str = "verse",
    play_drums: bool = False,
    output_device: int | None = None,
    master_level: float = 0.75,
) -> int:
    capture = MicrophoneCapture(device=device)
    analyzer: AudioAnalyzer | None = None
    follower = GrooveFollower(style=style, feel=feel, intensity=intensity, phrase=phrase)
    output = SampleOutput(device=output_device) if play_drums else None
    coordinator = PlaybackCoordinator(output) if output is not None else None
    try:
        if output is not None:
            output.set_master_level(master_level)
            try:
                output.start()
            except OutputError as exc:
                print(f"Drum output unavailable; continuing with analysis only: {exc}", file=sys.stderr)
                output = None
                coordinator = None
        capture.start()
        mode = "Live audio analysis and drum playback" if output is not None else "Live audio analysis"
        print(f"{mode} started. Press Ctrl+C to stop.")
        if output is not None:
            print("Playback keys: M mute/unmute, +/- master level, Q stop.")
        while True:
            if output is not None and poll_playback_controls(output):
                print("\nLive drum playback stopped.")
                return 0
            try:
                block = capture.read(timeout=1.0)
            except Empty:
                continue
            if analyzer is None:
                analyzer = AudioAnalyzer(block.sample_rate)
            observation = analyzer.process_block(block)
            if observation is None:
                continue

            decision = follower.update(observation)
            if coordinator is not None:
                coordinator.update(decision)
            tempo = f"{decision.tempo_bpm:.1f} BPM" if decision.tempo_bpm else "-- BPM"
            state = "holding last tempo" if decision.holding_stable_tempo else "tracking"
            if not decision.signal_active:
                state = "pause/no signal"
            pattern = " ".join(decision.pattern)
            print(
                f"t={observation.timestamp_seconds:6.1f}s | {tempo} "
                f"(confidence {decision.tempo_confidence:.2f}) | "
                f"energy {observation.combined_energy:.3f} | "
                f"intensity {decision.effective_intensity:.2f} | {state} | {pattern}"
            )
    except KeyboardInterrupt:
        print("\nLive microphone capture stopped.")
        return 0
    except (CaptureError, OutputError, OSError, ValueError) as exc:
        print(f"Unable to start live audio: {exc}", file=sys.stderr)
        return 1
    finally:
        capture.stop()
        if output is not None:
            output.stop()


def run_cli(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list_inputs:
        devices = list_input_devices()
        if not devices:
            print("No microphone input devices found.")
            return 0
        for device in devices:
            print(f"{device.index}: {device.name} ({device.channels} input channel(s), {device.sample_rate} Hz)")
        return 0
    if args.list_outputs:
        devices = list_output_devices()
        if not devices:
            print("No audio output devices found.")
            return 0
        for device in devices:
            print(f"{device.index}: {device.name} ({device.channels} output channel(s), {device.sample_rate} Hz)")
        return 0
    if args.live:
        if args.master_level < 0.0 or args.master_level > 1.0:
            raise SystemExit("--master-level must be between 0.0 and 1.0")
        return run_live(
            args.device,
            args.style,
            args.feel,
            args.intensity,
            args.phrase,
            args.play_drums,
            args.output_device,
            args.master_level,
        )
    if args.play_drums or args.output_device is not None:
        raise SystemExit("--play-drums and --output-device require --live")
    if args.interactive:
        return run_interactive()

    context = estimate_performance_context(
        tempo_hint=args.tempo,
        voice_energy=args.voice_energy,
        guitar_energy=args.guitar_energy,
        phrase=args.phrase,
    )
    groove = build_pattern(args.style, args.feel, args.intensity)
    accompaniment = generate_accompaniment(args.phrase, args.style, args.feel, args.intensity)

    print("Drum companion context")
    print(f"- Tempo: {context.tempo_bpm:.1f} BPM")
    print(f"- Phrase: {context.phrase}")
    print(f"- Confidence: {context.confidence:.2f}")
    print(f"- Suggested style: {args.style} / {args.feel}")
    print("- Groove pattern:", " ".join(groove[:8]))
    print("- Accompaniment preview:", " ".join(accompaniment[:8]))
    return 0
