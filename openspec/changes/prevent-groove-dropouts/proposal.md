# Proposal

## Why

The live companion can abruptly interrupt playback when a single analysis update reports weak confidence or low signal energy, even though the performer may only be taking a brief pause. Preserving the last stable groove briefly should make accompaniment feel continuous while still allowing it to fade out after sustained silence.

## What Changes

- When input remains active and onsets continue but tempo confidence is unreliable, retain the last stable tempo and groove until reliable tracking resumes.
- Treat a configurable period without detected onsets as musical inactivity even if RMS energy remains active.
- Expose the no-onset timeout in the CLI and as a live browser setting, with values of 0, 1, 2, or 4 bars and a default of 1 bar.
- Start inactivity transitions on the next downbeat, hold the groove for one complete bar, then fade its intensity to zero over the following complete bar.
- Cancel a pending fade when onsets return; resume on the next downbeat without resetting bar phase, ramping gain back over one beat.
- Keep reported analysis confidence unchanged; do not treat a confidence dip by itself as an instruction to stop playback.
- Preserve immediate stop behavior for explicit user stop and unrecoverable audio errors.

## Capabilities

### New Capabilities
- `drum-companion`: sustain and rejoin the live groove through brief signal and tempo-confidence interruptions, with configurable onset timeout and bar-aligned fade behavior.

### Modified Capabilities
- None

## Impact

- Affects live groove-following, CLI/browser settings, and bar-aligned scheduling in `drum_companion/audio/groove.py`, `drum_companion/control.py`, `drum_companion/app.py`, and potentially the decision model or scheduler.
- Requires regression coverage for confidence dips, active signal without onsets, mid-bar inactivity, fade, phase-preserving recovery, and the invariant that already-scheduled events do not move.
- No new runtime dependency is expected.