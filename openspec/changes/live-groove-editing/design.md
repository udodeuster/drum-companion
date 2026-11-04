# Design

## Context

See proposal.md - Why. The browser editor already edits saved grooves and posts explicit saves to the authenticated groove API. `LiveAudioController` persists those saves while running, then reads the selected groove again as live decisions arrive; `PlaybackCoordinator` applies updates to future unscheduled bars. Auto remains generated from live decisions, while the editor's existing copy path can convert an Auto pattern to a sixteen-step draft.

## Goals / Non-Goals

**Goals:**
- Make the current playback selection the natural starting point for the editor.
- Preserve the existing save confirmation boundary and live scheduling guarantees.
- Treat Auto editing as a snapshot saved into the named custom-groove library.

**Non-Goals:**
- Replace or mutate the Auto generator or its style/feel settings.
- Change the saved-groove data model, persistence format, or authenticated API.
- Allow preview audio to overlap live playback.

## Decisions

- **Initialize from the active playback selection.** On editor open, use the latest status settings to identify the selected saved groove and load that library entry into a draft with its stable ID. This makes Save update that groove rather than creating a duplicate. Keep the existing editor selector so users can still choose any other saved groove. An alternative was to add a separate edit action to every groove selector option; using the active selection as the editor default avoids duplicating selection controls.
- **Snapshot Auto without changing playback mode.** When Auto is selected, convert the latest available Auto pattern into the existing sixteen-step draft representation, using every other step for its eighth-note events. Leave the draft without a saved ID and require a name. Saving creates a named custom groove; Auto stays selected. This avoids turning a dynamic generator into a single static pattern or silently changing the selected playback source.
- **Use the existing explicit-save path during live playback.** Do not add a running-session guard to the save API. Continue to show a saved groove as saved only after the API confirms success. If the saved groove is selected, the existing live loop reloads it and scheduling uses it for future unscheduled bars; other saves remain in the library without changing the current selection. Already scheduled events remain untouched.
- **Retain preview/live mutual exclusion.** Editor changes can be saved during live playback, but preview remains unavailable until live playback stops, consistent with the existing preview lifecycle.
- **Verify both the browser workflow and scheduling boundary.** Add tests that editor initialization selects the active saved groove or builds an Auto snapshot, saving an Auto snapshot creates a named groove without selecting it, and saving the active groove during playback changes only future unscheduled bars.

## Risks / Trade-offs

- [The current Auto pattern may not yet be present in status when the editor opens] → Use the existing Auto-pattern endpoint fallback and keep the editor actionable when live analysis is waiting.
- [A user may mistake an Auto snapshot for a change to the Auto generator] → Require a groove name for saving and identify the result as a saved custom groove while leaving Auto selected.
- [A failed save could appear to apply live] → Keep the draft dirty until the API reports success and surface save errors through the existing control message.

## Migration Plan

No storage migration is needed. The feature uses the existing saved-groove format and API; existing grooves and Auto behavior remain unchanged.
