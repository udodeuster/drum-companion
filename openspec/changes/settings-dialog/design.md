# Design

## Context

See proposal.md for the motivation and specs/control-settings/spec.md for the behavior contract. The control page currently renders Audio Devices as a top-level section. Device and drum-playback settings already use the existing settings API and are rejected while a live session is active; Start/Stop remain in the main transport.

## Goals / Non-Goals

**Goals:**
- Keep the live view focused on transport, performance, and groove editing.
- Make device and playback configuration available through a clearly labeled gear control.
- Preserve existing settings values, API behavior, and session restrictions.

**Non-Goals:**
- Move groove, tempo, or performance controls into Settings in this change.
- Add persistence mechanisms or change which settings require a stopped session.
- Add a transport control inside Settings.

## Decisions

- **Use the existing native dialog pattern.** Add a gear button in the header and open a modal dialog titled Settings. This keeps navigation on the same page and provides a clear return path without another route or view state.
- **Move the existing Audio Devices section as a unit.** Keep microphone input, drum output, drum-playback toggle, and the existing device-change hint together so their relationships and existing IDs/event wiring remain intact.
- **Leave Start/Stop and live content outside the dialog.** When a session is running, explain in the dialog that the user must close it to reach Stop before changing devices or playback mode. This preserves the existing runtime restriction instead of adding transport duplication or changing backend behavior.
- **Keep the dialog available on desktop and phone layouts.** Reuse the page's responsive settings grid and give the dialog a constrained width and height with internal scrolling on short screens.

## Risks / Trade-offs

- [A modal can obscure the live state while open] → Keep the live-session indicator visible in the explanatory text and make closing the dialog straightforward.
- [Users may try changing a disabled-by-runtime setting during playback] → Show the stopped-session requirement in the dialog and preserve the API's existing actionable error.
- [Future settings may make the dialog too long] → Keep the content sectioned and scrollable; additional settings can be grouped later without altering this entry point.

## Migration Plan

No persisted settings or API migration is required. Move the controls without changing their identifiers or setting semantics.
