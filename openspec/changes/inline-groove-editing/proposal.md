# Proposal

## Why

Editing drum tracks currently requires opening a separate groove editor, so the active groove is not directly accessible for adjustment. Make the tracks immediately editable while preserving Auto's dynamic behavior and giving users clear choices to update or copy saved grooves.

## What Changes

- Show editable drum-step tracks directly in the Groove section without requiring a separate editor toggle.
- When Auto is selected, edit a snapshot of its current pattern; saving it creates a named groove and does not change Auto generation.
- For a saved groove, allow saving edits to the selected groove or saving them as a new named groove.

## Capabilities

### New Capabilities
- `groove-editing`: Direct editing and persistence of drum grooves in the control interface.

### Modified Capabilities
- None.

## Impact

- The browser control page's groove UI and save interactions.
- Groove save handling and tests, if needed to support the inline workflow.
