# Design

## Context

See proposal.md - Why and specs/drum-companion/spec.md for the behavior contract. The analyzer emits observations every 0.5 seconds and reports raw tempo confidence independently from short-window signal activity. The follower currently drops effective intensity to zero on the first inactive observation. The playback coordinator queues complete future bars, so changing event timing or mutating queued events is not an appropriate way to implement a smooth fade.

## Goals / Non-Goals

**Goals:**
- Retain the last stable tempo and groove while active input produces temporarily unreliable estimates.
- Bound playback retention when RMS remains active but musical onsets stop, with a timeout configurable at startup and during browser control.
- Hold a stable groove for one bar after input becomes inactive, then fade smoothly over one bar if inactivity continues.
- Align hold, fade, and recovery to downbeats while preserving scheduled event positions and immediate user stop behavior.

**Non-Goals:**
- Change onset detection, the RMS activity threshold, or the raw confidence calculation without separate evidence.
- Add dependencies or change audio-device lifecycle.

## Decisions

- Model playback continuity separately from tempo confidence. A low-confidence or discontinuous observation with continuing onsets keeps the last stable tempo and groove; raw observation confidence remains unchanged.
- Add a no-onset timeout setting with values of 0, 1, 2, or 4 bars, defaulting to 1. Expose it as `--onset-timeout-bars` for CLI startup and through the browser settings API/page for live adjustment. Count bars from the last detected onset using the last stable tempo.
- Classify the session as musically inactive when RMS falls below the current threshold or the configured no-onset timeout expires. A zero-bar timeout makes the first onset gap eligible immediately; the common transition still waits for the next barline.
- Use the playback scheduler's bar clock to align transitions. When inactivity is detected mid-bar, continue the current groove until the next downbeat; hold one complete bar, then linearly reduce gain to zero over the following complete bar.
- Cancel the pending silence transition when onsets resume. Continue the current bar phase rather than restarting the pattern, and restore gain over one beat to avoid an amplitude step. Existing queued event frame positions remain unchanged.
- Apply fade as a frame-based output envelope in the audio callback, independent of user master level and mute. The coordinator may keep already queued hits at their original frame positions; the envelope attenuates their rendered audio without moving them. Once the fade completes, the follower emits no further audible groove events until activity resumes.
- Keep explicit stop and unrecoverable capture/output errors outside the grace/fade state; they stop immediately.

## Risks / Trade-offs

- [Sparse playing may be mistaken for inactivity] → Let users select a longer onset timeout in bars and preserve the raw confidence measurement for diagnosis.
- [Downbeat alignment extends the audible hold after mid-bar detection] → Document and test that transitions occur only at barlines; the bounded extension is intentional to preserve musical phrasing.
- [Queued events extend beyond a state transition] → Apply the fade in the output callback rather than rewriting or retiming queued events.

## Migration Plan

No migration is required. The behavior changes only during low-confidence and inactive-signal intervals; explicit stop and device handling remain unchanged.