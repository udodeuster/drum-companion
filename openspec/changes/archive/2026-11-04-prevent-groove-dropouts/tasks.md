# Tasks

## 1. Preserve Groove During Tempo Uncertainty

- [x] 1.1 Add a validated no-onset timeout setting (0, 1, 2, or 4 bars; default 1) to CLI startup and live settings; verify defaults, validation, CLI propagation, and browser updates with focused tests.
- [x] 1.2 Update follower decisions so active low-confidence observations with continuing onsets retain the last stable tempo and groove, while active RMS with no onsets expires at the configured timeout; verify confidence remains raw and tests cover every timeout choice.

## 2. Downbeat-Aligned Hold, Fade, and Recovery

- [x] 2.1 Align inactivity transitions to the next scheduler downbeat; verify a mid-bar pause completes the current bar, followed by one full hold bar and one full fade bar.
- [x] 2.2 Apply a frame-based fade envelope independently of master level and mute; verify recovery cancels the fade, preserves the running bar phase, ramps gain over one beat, and never moves queued events.
- [x] 2.3 Document CLI and browser timeout controls plus downbeat-aligned hold/fade/recovery in the README; verify examples and defaults match the spec.

## 3. Integration Verification

- [x] 3.1 Add or extend end-to-end tests from analyzer observations through follower, coordinator, and rendered output; verify active noise without onsets for each configured timeout, mid-bar silence, fade, phase-preserving recovery, and immediate explicit stop.
- [x] 3.2 Run focused audio/input/output/web tests and the full suite; verify all tests pass and smoke-test sparse input, brief silence, sustained silence, and recovery when audio hardware is available.