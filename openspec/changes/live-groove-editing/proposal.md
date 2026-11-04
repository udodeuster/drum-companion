# Proposal

## Why

Performers need to adjust the groove they are currently hearing without stopping a live session or rebuilding it through a separate copy workflow. Auto is generated dynamically, so users also need a clear way to edit its current pattern and keep that variation for later.

## What Changes

- Let the editor start directly from the current playback selection, including any saved groove selected during a live session.
- Keep saved-groove edits explicitly saved, and make the edited version available for live playback from the next unscheduled bar without moving already scheduled events.
- When Auto is selected, load its current generated pattern into the editor as an editable snapshot; saving that snapshot creates a named custom groove and leaves Auto generation unchanged.
- Keep groove editing and saving available during live playback; preview remains subject to its existing live-session restriction.

## Capabilities

### New Capabilities

- `groove-library`: Directly edit the active saved groove or an editable snapshot of Auto, explicitly save changes, and use saved changes during live playback.

### Modified Capabilities

None. The project has no canonical capability specs yet; the existing `groove-library` requirements are change-local.

## Impact

- Paired browser control page: editor entry point, draft initialization, and save feedback.
- Existing groove save API and host-local library; Auto snapshots save as named custom grooves rather than replacing the generator.
- Live controller and playback scheduling: retain next-unscheduled-bar updates and queued-event timing.
- Browser, controller, audio scheduling, and groove-library tests; README groove-editing guidance.
