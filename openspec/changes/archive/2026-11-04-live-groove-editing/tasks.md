# Tasks

## 1. Active Groove Editor Workflow

- [x] 1.1 Initialize the editor from the selected saved groove or the latest Auto pattern snapshot; verify saved-groove steps/levels and Auto's even-step conversion with browser-facing tests.
- [x] 1.2 Save an edited Auto snapshot as a named custom groove without changing the selected Auto playback mode; verify creation and selection state through control/API tests.
- [x] 1.3 Update README groove instructions for direct editing, live saving, and named Auto snapshots; verify the documented steps match the control page.

## 2. Live Save and Playback

- [x] 2.1 Verify that saving the selected groove is allowed during live playback and that its saved revision is used only for future unscheduled bars; cover controller and scheduler behavior with regression tests.
- [x] 2.2 Verify that saving a non-selected groove during live playback preserves the current selection and leaves the active playback pattern unchanged.

## 3. Integration Verification

- [x] 3.1 Run the focused groove-library, control, audio-output, and web test suites together; verify Auto, saved-groove editing, live save timing, and error handling remain consistent.
