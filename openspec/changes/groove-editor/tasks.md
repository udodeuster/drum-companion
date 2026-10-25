# Tasks

## 1. Groove Data and Persistence

- [x] 1.1 Define and validate the saved-groove model (stable ID, unique non-empty name, five tracks, sixteen boolean steps, bounded track levels); verify valid and invalid cases with unit tests.
- [x] 1.2 Implement versioned host-local library loading and explicit atomic saves; verify restart persistence, duplicate-name rejection, and reported read/write failures with repository tests.

## 2. Audio Scheduling and Mixing

- [x] 2.1 Extend groove event conversion to support authored sixteen-step bars while preserving existing eight-step Auto timing; verify both resolutions, bar length, and relaxed eighth-note swing with audio tests.
- [x] 2.2 Apply per-track levels and shared intensity before the existing master output level; verify independent track gains, zero-level silence, and unchanged master-level behavior with mixer tests.
- [x] 2.3 Route selected saved patterns through live tempo/activity decisions and apply edits only to future unscheduled bars; verify Auto remains unchanged and queued events retain their frame positions with controller/scheduler tests.

## 3. Paired Control and Editor

- [x] 3.1 Add authenticated control operations to list and explicitly save grooves, returning clear validation and storage errors; verify session/origin checks and error responses with web API tests.
- [x] 3.2 Add the responsive editor and main-view selector for Auto and named grooves, including blank/copy-from-Auto drafts, per-track controls, unsaved-change indication, and explicit save; verify browser-facing behavior and 16-step layout with UI tests.
- [x] 3.3 Document groove creation, editing, selection, and local persistence in README.md; verify the documented workflow matches the controls and playback modes.

## 4. Integration Verification

- [x] 4.1 Run the focused groove, output, controller, and web test suites together; verify Auto playback, saved-groove playback, swing, track levels, and save/reload behavior remain consistent end to end.
