# Tasks

## 1. Musical Test Inputs

- [x] 1.1 Add deterministic guitar-strum-like, vocal-phrase-like, and sparse onset fixtures, including half/double-time ambiguity; verify fixture ground truth and repeatability in the audio-analysis test path.
- [x] 1.2 Add an offline playback comparison path for tight/relaxed candidate grooves across the bundled kit; verify candidates render without audio hardware and keep event timing inspectable.

## 2. Groove Feel, Dynamics, and Variation

- [x] 2.1 Separate core kick/backbeat events from supplementary events and apply nonzero intensity changes without deleting the core; verify patterns remain structurally recognizable across the supported intensity range.
- [x] 2.2 Implement tight and relaxed timing/articulation as distinct bounded behaviors while preserving core accents; verify timing bounds and backbeat continuity with focused groove tests.
- [x] 2.3 Add reproducible, style-appropriate bar variation in accents, articulation, or ghost notes without altering the core pulse; verify repeated bars vary and remain within documented bounds.
- [ ] 2.4 Audition all three styles at low and high nonzero intensity with representative guitar/voice-like material; record musician decisions for timing and ghost-note bounds, tune defaults accordingly, and verify tests/documentation match the accepted behavior.
- [x] 2.5 Document tight/relaxed and intensity semantics in the README and browser controls; verify descriptions match audible behavior and existing defaults remain unchanged.

## 3. Tempo and Sparse-Input Following

- [x] 3.1 Add pulse-stability hysteresis for ambiguous half/double-time evidence; verify ambiguous fixtures do not cause unsupported octave jumps and sustained genuine tempo shifts still update future bars.
- [x] 3.2 Validate sparse guitar and vocal phrase fixtures against no-onset timeout values 0, 1, 2, and 4; verify the groove persists within the selected grace period and inactivity begins on the specified downbeat.
- [x] 3.3 Document pulse-stability behavior and the sparse-input timeout tradeoff; verify the CLI and browser descriptions agree with the tested behavior.

## 4. End-to-End Musical Verification

- [x] 4.1 Extend the analyzer-to-follower-to-scheduler/output integration tests for sparse input, tempo ambiguity, phrase recovery, hold, fade, and explicit stop; verify queued events retain their positions and stop remains immediate.
- [ ] 4.2 Run the focused audio-analysis, groove, output, and web tests plus the full suite; complete a musician listening check and record any recovery-lag concerns as follow-up rather than changing the current transition contract.