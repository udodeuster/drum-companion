# Design

## Context

See proposal.md for the motivation and specs/groove-editing/spec.md for the user-visible contract. The control page already has a step-grid editor, an unsaved-draft model, and a save endpoint that updates a groove when given its ID or creates one when the ID is omitted. Today, the editor is hidden behind a button and offers a copy of Auto as a draft.

## Goals / Non-Goals

**Goals:**
- Reuse the existing track grid and draft behavior in the main Groove section.
- Make the current saved groove the editable target, or initialize an Auto snapshot when Auto is selected.
- Offer distinct actions to update the selected saved groove or create a named copy.

**Non-Goals:**
- Persist user edits into the Auto-generation algorithm.
- Change groove timing, track layout, or the Auto pattern-generation rules.
- Add a new storage format or API endpoint unless implementation reveals an existing interface limitation.

## Decisions

- **Move the existing editor surface into the Groove section rather than add a second editor.** This keeps step toggling, level controls, preview, and unsaved-change handling consistent. The separate open/close control is no longer needed for editing.
- **Keep edits in a draft until the user chooses a save action.** The current target provides the starting pattern; changing targets while the draft is dirty must continue to prompt before discarding it.
- **Treat Auto as a snapshot source.** Auto is generated dynamically from performance and settings, so editing it must not create persistent overrides that conflict with generation. Saving an Auto snapshot creates a named saved groove.
- **Use the existing save API for both persistence paths.** Include the current ID to update a saved groove; omit it to create a new groove. “Save as” must omit the source ID and use the user-provided name.

## Risks / Trade-offs

- [Inline grid takes more vertical space on phones] → Reuse the existing responsive track-grid layout and keep each track's steps horizontally scrollable.
- [A save-as action could accidentally overwrite the source] → Keep update and save-as actions distinct, and test that save-as creates a different ID while leaving the source unchanged.
- [Polling or target changes could replace unsaved edits] → Preserve the current dirty-draft guard when refreshing groove choices and switching targets.

## Migration Plan

No persisted data migration is expected. Existing saved grooves and the current groove storage format remain unchanged.
