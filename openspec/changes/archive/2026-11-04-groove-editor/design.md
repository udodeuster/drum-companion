# Design

## Context

See proposal.md - Why. The local browser panel is served by the Python host and all control requests require the paired session. `GrooveFollower` currently produces eight eighth-note cells; `GrooveScheduler` turns them into timed events and `SampleOutput` applies event velocity, mute, and master level. There is no persistent groove library or per-instrument gain.

## Goals / Non-Goals

**Goals:**
- Add an editable, persistent library without changing the automatic mode's existing eight-step patterns.
- Preserve live tempo/activity following and bar phase for both automatic and saved grooves.
- Keep the editor usable from the existing phone and host-browser control page.
- Keep storage local to the host and require explicit confirmation before replacing a saved groove.

**Non-Goals:**
- User-loaded samples, arbitrary instrument tracks, per-hit velocity editing, song arrangement, MIDI, cloud sync, or collaborative editing.
- Persisting general live-audio settings; only saved grooves are in scope.

## Decisions

- **Represent authored grooves separately from generated patterns.** A saved groove has a stable ID, a display name, sixteen boolean steps for each of the twelve bundled instruments (grooves saved with the original five load with empty extra tracks), and a level per instrument. This avoids changing the existing generated eight-cell pattern contract. The editor keeps a draft until the user explicitly saves it; blank and copy-from-Auto creation paths both produce drafts.
- **Use host-local versioned JSON storage.** Store the library under the user's application-data directory (on Windows, `%LOCALAPPDATA%\\DrumCompanion\\grooves.json`). Validate the complete document on load and save, serialize writes under a lock, and replace the file atomically. Keep the repository path injectable for tests. Reject empty or case-insensitively duplicate names rather than overwriting another groove.
- **Extend the paired control surface.** Add authenticated operations to list and save grooves, and expose an editor reachable from the live control page. The main selector contains Auto and saved groove names. Keep draft editing in the page; only a validated explicit save changes the persistent library. Continue using the existing session and same-origin checks.
- **Keep live analysis and playback selection separate.** Continue feeding microphone observations through `GrooveFollower` for tempo, confidence, and activity. At the playback boundary, Auto uses its current generated pattern; a saved selection supplies its stored steps and levels. Do not let generated style updates overwrite an authored pattern.
- **Generalize event timing by grid resolution.** Keep eight Auto cells as eighth notes and schedule sixteen authored cells as sixteenths, with both spanning the same four-beat bar. Copying Auto places its eighth-note events at custom-grid indices 0, 2, 4, through 14. In relaxed feel, delay custom-grid eighth-note offbeats at indices 2, 6, 10, and 14 by the existing 5% of a beat; leave other authored positions unchanged.
- **Apply gains at the event boundary.** Multiply each event by its instrument's saved track level and the existing shared intensity scale before mixing; preserve master level as the independent final output control. A zero track level silences only that instrument.
- **Preserve scheduling guarantees.** Selection or saved edits update future unscheduled bars only. Events already queued keep their frame positions, and the current downbeat/bar phase is not reset.
- **Give editor audition its own microphone-free playback lifecycle.** The controller owns a preview worker that opens the selected host output, loads the same bundled kit, and schedules the current in-memory draft without creating a microphone capture or changing the selected live groove. Preview and live session are mutually exclusive; reject preview start with an actionable message while live is active, and stop/close the preview stream explicitly.
- **Use an adjustable preview tempo.** Initialize from the most recently available analyzed tempo, including the stopped session's retained status, or 100 BPM when none exists. Validate manual values using the supported 30-300 BPM range. The browser sends the current draft and tempo to the host; the phone remains a remote control and audio still comes from the host output.
- **Apply draft revisions at bar boundaries.** While looping, the preview worker keeps already scheduled events unchanged and reads the latest in-memory draft and track levels when it schedules each next bar. Editing never writes to the persistent library; explicit groove save remains separate.

## Risks / Trade-offs

- [Invalid or partially written library data could make saved grooves unavailable] -> Validate the whole document, write atomically, surface a clear error, and never silently replace invalid data with an empty library.
- [A sixteen-cell row can be cramped on a phone] -> Use compact tap targets and a responsive grid with step numbers; keep each instrument and its level visually grouped.
- [Track level and shared intensity can be mistaken for the same control] -> Label them distinctly and document that track level sets the instrument balance while intensity scales all custom events.
- [Future scheduling queues events ahead of playback] -> Apply edits at unscheduled bar boundaries and test that queued events retain their original timing.
- [Preview output initialization or shutdown can fail] -> Surface actionable output errors, keep preview state truthful, and guarantee stream cleanup on stop or worker failure.
- [A user may expect preview sound on the paired phone] -> Label the control as host-output preview and explain that the phone only controls the host playback.

## Migration Plan

There is no existing saved-groove data to migrate. The library starts empty; Auto remains available and continues to use the current generator. If storage cannot be read or written, report the error and do not claim a save succeeded.
