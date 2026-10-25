# Proposal

## Why

The live companion can generate and play grooves, but performers cannot shape individual drum tracks or keep named grooves for later sessions. A small, persistent groove library and step editor will let users prepare grooves while preserving the existing automatic accompaniment mode.

## What Changes

- Add a browser-based groove editor with a 16-step grid for kick, snare, closed hi-hat, open hi-hat, and cymbal tracks.
- Allow each step to be toggled and each track to have an independent level.
- Let users create a groove from an empty grid or copy the current automatic groove, name it, edit it, and explicitly save it.
- Provide an independent looping preview of the current unsaved editor draft, with adjustable BPM and bar-boundary updates as the draft changes.
- Persist the groove library on the host computer and expose saved grooves in the live control page.
- Keep the automatic groove mode available. When a saved groove is selected, retain live tempo and activity detection while playing its fixed step pattern.
- Apply the existing intensity setting as a shared scale across custom-groove hits; keep master output level independent.

## Capabilities

### New Capabilities

- `groove-library`: Create, edit, persist, select, and play named user-authored drum grooves.

### Modified Capabilities

None. The repository currently has no canonical capability specs; existing groove and audio-output requirements are change-local deltas.

## Impact

- Browser control page and its authenticated local API.
- Groove representation, event scheduling, and sample mixing for step resolution and per-track levels.
- Host-local persistent storage for named grooves.
- A preview-only playback mode sharing the host audio output without requiring microphone capture.
- Tests for editing, validation, persistence, selection, playback behavior, and preservation of automatic mode.
