# Proposal

## Why

The current prototype accepts tempo and energy values as command-line hints, so it cannot respond to an actual solo guitar + voice performance. A microphone-backed analysis pipeline is needed to provide measured timing and dynamics to the groove engine, while reporting uncertainty instead of inventing musical context when the signal is ambiguous.

## What Changes

- Add a live audio input path for a single mixed microphone signal, including input-device selection and graceful handling of unavailable or failed devices.
- Analyze the stream for onset timing, tempo, overall performance energy, and likely acoustic phrase breaks, with confidence attached to estimates.
- Provide a stable analysis result interface that the existing groove engine can consume and update as the performer plays.
- Support repeatable analysis of recorded audio clips for tests and tuning; live audio remains in memory and is not saved by default.
- Keep source separation, independent guitar/vocal energy, chord recognition, and automatic verse/chorus classification out of v1; phrase breaks are acoustic candidates, not song-section labels.

## Capabilities

### New Capabilities

- `audio-analysis`: capture a mixed live input and produce confidence-aware rhythmic and overall-dynamics estimates for accompaniment.

### Modified Capabilities

- None

## Impact

- Replaces numeric-only performance hints with a stream-based analysis source while keeping a defined boundary to the existing groove engine.
- Adds Windows desktop microphone capture and Python signal-analysis dependencies, plus deterministic audio-clip tests.
- Affects CLI interaction for selecting and starting/stopping capture and reporting device or signal errors.
- Android packaging and capture are deferred; this change does not claim Android support.
