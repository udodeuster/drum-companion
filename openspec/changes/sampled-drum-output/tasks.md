# Tasks

## 1. Starter kit and event contract

- [x] 1.1 Add bundled kick, snare, closed/open hi-hat, and cymbal one-shots plus a per-file source/license manifest; verify every asset is loadable offline and has approved redistribution terms.
- [x] 1.2 Define the conversion from groove pattern cells to timed drum events and accent-derived velocities; verify tests cover kick/snare/hat mapping and controlled open-hat/cymbal variations without treating the accent marker as an instrument.

## 2. Sample renderer and output devices

- [x] 2.1 Implement sample preloading, format conversion, normalization, and overlap mixing with velocity/master gain; verify tests cover overlapping voices, bounded peaks, and silence when muted or stopped.
- [x] 2.2 Add output-device enumeration/selection and stream lifecycle using a bounded audio callback; verify tests cover successful selection, unavailable devices, callback output, and actionable startup errors, and document the device commands.

## 3. Event scheduling and controls

- [x] 3.1 Schedule groove events against output-frame time and apply reliable tempo changes only to unscheduled events; verify tests show stable scheduled frame positions and updated future spacing after tempo changes.
- [x] 3.2 Implement start, stop, master-level, and immediate-mute controls; verify tests show stop clears pending hits, mute silences subsequent frames, and level changes do not alter event timing.

## 4. Companion integration

- [x] 4.1 Connect live GrooveDecision updates to the scheduler and carry groove dynamics into sample velocities; verify fixture-driven tests exercise reliable tempo, low-confidence behavior, and recovery through the renderer.
- [x] 4.2 Document the live output workflow, selected-device setup, sample-kit provenance policy, and the fact that guitar/voice input is not monitored through the drum output; verify each documented command matches CLI help.

## 5. End-to-end validation

- [x] 5.1 Run offline end-to-end tests from known analysis fixtures through groove scheduling and sample mixing; verify event timing, tempo update behavior, mute/stop, and asset loading without audio hardware.
- [x] 5.2 Perform and document a Windows output-device smoke test; verify selected-device playback is audible, controls work during playback, and a device failure leaves analysis/preview available with an actionable message.
