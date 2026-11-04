# Proposal

## Why

The current groove engine produces symbolic patterns but no audible backing, so the solo guitar + voice performer cannot hear or rehearse with the rhythm companion. This change adds self-contained sampled drum playback that follows the generated groove through a user-selected Windows audio output.

## What Changes

- Add a Windows desktop audio-output capability that renders groove events as drum audio through a selected output device.
- Bundle a small starter drum kit that is available offline and whose assets have clear redistribution rights and recorded provenance.
- Provide output-device listing/selection and playback start, stop, master-level, and immediate-mute controls.
- Schedule pattern events against the current tempo and apply velocity/dynamic changes while avoiding shifts to events already scheduled.
- Keep the output backend behind a replaceable boundary so other output modes can be added later without including them in v1.
- Keep MIDI output, user-provided sample libraries, Android packaging, and multi-output routing out of this change.

## Capabilities

### New Capabilities

- `audio-output`: render the drum companion's groove as sampled audio to a selected output device with basic playback controls.

### Modified Capabilities

- None

## Impact

- Adds a Windows audio output stream, sample loading/mixing, an event scheduler, and an output-device control path.
- Adds bundled audio assets plus a manifest documenting each asset's source and license.
- Connects `GrooveDecision` pattern, tempo, and intensity to audible playback while retaining the existing analysis and groove interfaces.
- Does not claim Android support or add MIDI output in v1; the backend boundary leaves those as possible future capabilities.
