# Tasks

## 1. Analysis contract and dependencies

- [x] 1.1 Add the immutable audio-analysis observation model and replace unsupported separate guitar/vocal energy assumptions; verify unit tests cover timestamps, normalized combined energy, and independent confidence values.
- [x] 1.2 Add and document the selected audio capture and signal-analysis dependencies; verify they install in the supported Python environment without requiring an audio device.

## 2. Live input lifecycle

- [x] 2.1 Implement microphone enumeration/selection, start/stop lifecycle, and bounded callback-to-worker buffering; verify tests cover unavailable devices, capture errors, and queue overflow without blocking or stale live results.
- [x] 2.2 Add CLI commands for listing inputs and starting/stopping live analysis, plus setup documentation; verify help/device-list output and documented commands work without a microphone attached.

## 3. Signal analysis

- [x] 3.1 Implement shared audio-block processing for live and WAV sources, producing timestamped onsets, tempo/confidence, and normalized combined energy; verify known-pulse fixtures converge on expected tempo and preserve onset timestamps through tempo changes.
- [x] 3.2 Add silence/ambiguity confidence handling and acoustic phrase-break candidates; verify fixtures cover pauses, noisy/irregular input, and that no verse/chorus label is inferred.

## 4. Groove integration and privacy

- [x] 4.1 Feed analysis observations into the groove engine and use confidence-aware hold/reduced-activity behavior; verify integration tests show stable playback state during low-confidence input and updates after reliable tempo changes.
- [x] 4.2 Keep microphone buffers transient and ensure the live path writes no recordings; verify a start/stop session leaves no audio artifact and document the privacy behavior.

## 5. End-to-end validation

- [x] 5.1 Run the full fixture-driven analysis-to-groove scenario across steady pulse, tempo shift, phrase pause, and recovery; verify all expected observations and fallback behavior in the automated suite.
- [x] 5.2 Perform and document a live microphone smoke test on a supported desktop setup; verify device selection, start/stop, visible analysis updates, and actionable failure reporting.
