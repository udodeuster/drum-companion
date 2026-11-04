# Design

## Context

See proposal.md - Why. The current Python application analyzes microphone input with `sounddevice`, computes tempo and combined energy with librosa, and translates observations into a symbolic `GrooveDecision`. `GrooveDecision.pattern` is a tuple of compact strings; no sample playback, output-device selection, event scheduler, or mixer exists. The current project targets Windows desktop; Android is deferred by user decision.

## Goals / Non-Goals

**Goals:**
- Turn generated groove patterns into predictable audible one-shot drum events.
- Let users choose an output device and control playback without tying audio timing to analysis computation.
- Keep sample assets available offline and ensure every redistributed asset has documented rights and provenance.
- Keep playback behind a replaceable output boundary for possible future MIDI or mobile work.

**Non-Goals:**
- MIDI output, DAW integration, user sample-pack loading, Android support, or multiple simultaneous output devices.
- Playing or monitoring the guitar/voice input through the output stream.
- A full drum sequencer or editable song-arrangement UI.

## Decisions

- **Reuse `sounddevice` for Windows output.** Use its `OutputStream` with the already-declared PortAudio dependency and enumerate output-capable devices independently from microphone inputs. An external MIDI backend was considered, but requires a DAW or hardware and does not meet the self-contained audible-playback goal.
- **Bundle a small WAV starter kit.** Include kick, snare, closed and open hi-hat, and cymbal one-shots. Accept only original recordings with documented project rights or assets with clear redistribution rights (prefer CC0); keep a manifest with source, author, license, and attribution/terms for every file. Do not bundle an asset whose redistribution terms are uncertain.
- **Separate groove scheduling from audio rendering.** Convert the current symbolic pattern to timed drum events (kick, snare, closed hat, open hat, cymbal) with accent-derived velocity. A scheduler consumes `GrooveDecision` updates and queues future events; the output callback only mixes already-loaded sample data into the requested frames. It must not decode files, perform librosa analysis, or wait on blocking work.
- **Keep a short scheduling horizon.** Queue upcoming events against output-frame time. A reliable tempo update changes events not yet scheduled; existing events retain their frame positions. This avoids moving active hits while still following the performer.
- **Mix sample voices in memory.** Load and normalize the small kit before playback. The output callback sums overlapping sample voices, applies per-hit velocity and master level, clamps the final signal, and outputs silence when stopped or muted. Convert/resample assets once during loading if the selected device format differs; never resample or load assets inside the callback.
- **Keep controls orthogonal to groove timing.** Output-device selection is established before stream start. Master level and immediate mute apply to subsequent output frames; stop clears pending events and closes the stream cleanly.
- **Preserve the current pattern interface initially.** Translate its symbolic cells at the audio-output boundary so existing CLI previews remain usable. If richer articulation requires typed events, introduce them behind that boundary and preserve equivalent preview behavior.

## Risks / Trade-offs

- [A Python output callback can underrun or produce jitter under load] → Keep the callback bounded and allocation-light, schedule ahead by a short configurable horizon, and test callback behavior with overlapping voices and representative sample rates.
- [Bundled sample rights can be unclear] → Require a reviewed per-file manifest and accept only original or clearly redistributable assets; keep this as a release gate.
- [Separate microphone and output devices may use different clocks] → Schedule from output-frame time and treat input-derived tempo as musical guidance rather than assuming input and output clocks are sample-synchronous.
- [Tempo changes can make queued events feel late or abrupt] → Update only unscheduled events and apply tempo changes at the next event boundary.
- [Mixing multiple samples can clip] → Normalize source assets, apply velocity/master gain, and clamp or limit the mixed output; verify peak bounds in tests.
- [Current symbolic patterns do not encode every bundled instrument] → Define and test explicit mapping for existing kick/snare/hat/accent tokens; keep optional open-hat/cymbal events as controlled groove variations rather than misreading accent markers as instruments.

## Migration Plan

Add sampled output as an explicit live-playback mode while keeping existing input-only and manual preview modes available. The new renderer consumes groove decisions through an adapter; no existing analysis or groove callers need output-device dependencies. If playback is disabled or device initialization fails, the existing analysis and text preview remain available and the CLI reports the output failure.
