# Tasks

## 1. Inline groove editing

- [x] 1.1 Move the existing step grid and track-level controls into the Groove section, initialize it from the selected saved groove or an Auto snapshot, and update the UI guidance; verify `tests.test_web` covers the inline controls and Auto snapshot behavior.
- [x] 1.2 Preserve unsaved edits when status and groove options refresh, and retain confirmation before discarding a dirty draft; verify the focused control-page tests cover refresh and target switching.
- [x] 1.3 Send unsaved track and level edits to the live controller and apply them to future output bars; verify the Auto draft overrides generated playback without changing Auto or saved grooves.

## 2. Groove save actions

- [x] 2.1 Add distinct actions to update the selected saved groove or save the draft under a new name, using the existing ID-based update and ID-less create behavior; verify `tests.test_web` and `tests.test_control` cover updating, creating a copy, and saving an Auto snapshot without changing its source.
- [x] 2.2 Verify user-facing validation and error reporting for missing names or failed saves remain visible; verify the focused save-flow tests cover these cases.

## 3. Integration verification

- [x] 3.1 Run the complete test suite with `python -m unittest discover -s tests` and manually verify inline editing, updating a saved groove, saving a copy, and editing Auto without altering Auto generation.
