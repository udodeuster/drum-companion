# Design

## Context

See proposal.md - Why. The project is currently a Python 3.11+ CLI prototype. `estimate_performance_context` accepts manually supplied tempo and energy values; it has no microphone capture, stream lifecycle, or audio-derived confidence. The existing `PerformanceContext` has separate voice and guitar energy fields, which cannot truthfully be populated from the selected single mixed-microphone input.

## Goals / Non-Goals

**Goals:**
- Add a replaceable audio source boundary for device capture and deterministic recorded-clip input.
- Turn audio blocks into timestamped onset events, a confidence-aware rolling tempo estimate, combined signal energy, and acoustic phrase-break candidates.
- Keep the capture callback responsive and avoid blocking audio-device work on analysis.
- Define a result model the groove engine can consume without relying on fabricated or stale estimates.

**Non-Goals:**
- Source separation, vocal/guitar classification, chord recognition, or automatic verse/chorus labels.
- Saving or streaming microphone recordings.
- Drum playback, audio mixing, or a graphical interface.
- Android packaging or device capture; the current Python implementation targets Windows desktop, with mobile support deferred.

## Decisions

- **Use one mixed mono analysis channel.** Convert device input to mono when necessary and measure combined energy. Separate tracks or source-separation models were considered, but add substantial complexity and are not needed for initial pulse-following.
- **Separate capture from analysis.** Use `sounddevice`/PortAudio to enumerate and capture Windows input devices. The audio callback only copies frames into a bounded queue; a worker consumes blocks and runs feature extraction. Queue overflow becomes an explicit discontinuity/low-confidence condition instead of blocking the callback.
- **Use rolling-window librosa analysis rather than a native aubio build.** Compute onset strength and tempo from a bounded rolling audio window with librosa, and compute normalized windowed RMS with NumPy. Recompute on overlapping windows so the estimates can follow performance changes while keeping the processing out of the device callback. This avoids aubio's failing Windows source build and keeps the analysis path in the existing Python stack. Do not label song sections.
- **Make one block processor the source of truth.** Both live microphone blocks and WAV test fixtures pass through the same analysis interface, with sample-count-derived timestamps. This enables repeatable tests without hardware and prevents separate live/test implementations from drifting.
- **Emit immutable observations with independent confidence.** Each update carries its timestamp, new onset events, tempo and tempo confidence, normalized combined energy, and optional phrase-break candidate/confidence. Downstream groove behavior may retain the last stable tempo or reduce activity when confidence falls; it must not treat an uncertain estimate as a new tempo.
- **Keep raw samples transient.** The capture queue and analysis window are bounded; no recording is written to disk. WAV input is only a test/analysis source selected by the caller.
- **Provide an explicit stream lifecycle.** Device enumeration/selection, start, stop, and device errors are surfaced through the CLI. Keep the existing numeric CLI mode available as a deterministic manual/demo path during transition.

## Risks / Trade-offs

- [Microphone quality, room noise, and simultaneous voice/guitar can confuse onset tracking] → Expose confidence, test quiet/noisy/irregular fixtures, and use conservative fallback behavior.
- [Librosa rolling-window computation may add latency or CPU load] → Keep the window bounded, benchmark update cadence on Windows, and tune window/hop sizes against fixture tests.
- [Android packaging and low-latency capture are not supported by this Python desktop slice] → Keep capture behind an adapter and defer Android-specific packaging until it is explicitly in scope.
- [Queue overflow can lose timing continuity] → Bound memory, report the discontinuity, and lower confidence until the tracker stabilizes again.
- [Tempo trackers can report half/double-time interpretations] → Validate representative clip fixtures and preserve confidence rather than silently presenting ambiguous tempo as certain.
- [Acoustic phrase breaks are not equivalent to song sections] → Report only pause/activity-change candidates; leave verse/chorus selection to user control.

## Migration Plan

Keep the current CLI hint-based mode working while adding an explicit live-capture mode. Integrate the new observation model with the groove engine behind a clear source boundary; remove the old fields only after callers no longer rely on separate voice/guitar energy values. No existing recordings or persistent data require migration.
