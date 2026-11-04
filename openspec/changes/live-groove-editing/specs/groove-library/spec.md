# Spec Delta

## Purpose

The groove library lets performers edit the groove they are using, preserve named variations, and make saved changes available without interrupting live tempo following.

## ADDED Requirements

### Requirement: Open the active playback groove for editing
The system SHALL initialize the editor from the current playback selection when the user opens it.

#### Scenario: Edit the active saved groove
- **WHEN** a user opens the editor while a saved groove is selected
- **THEN** the editor SHALL load that groove's name, steps, and track levels for direct editing

#### Scenario: Edit the current Auto groove
- **WHEN** a user opens the editor while Auto is selected
- **THEN** the editor SHALL load the latest available Auto pattern as a sixteen-step editable snapshot, placing its eighth-note events on every other step

### Requirement: Save an Auto snapshot as a named groove
The system SHALL save edits made to an Auto snapshot as a named custom groove without changing Auto generation.

#### Scenario: Save an edited Auto snapshot
- **WHEN** a user names and saves an edited Auto snapshot
- **THEN** the system SHALL create a persistent named groove from the snapshot and SHALL leave Auto behavior unchanged

#### Scenario: Keep Auto selected while saving its snapshot
- **WHEN** a user saves an Auto snapshot during a live session
- **THEN** the system SHALL keep Auto selected for playback unless the user explicitly selects the newly saved groove

### Requirement: Save groove edits during live playback
The system SHALL allow a user to explicitly save edits to a saved groove without stopping live playback.

#### Scenario: Save the active groove during playback
- **WHEN** a user saves edits to the saved groove currently selected for live playback
- **THEN** subsequent unscheduled bars SHALL use the saved changes and already scheduled events SHALL retain their timing

#### Scenario: Save a different groove during playback
- **WHEN** a user saves edits to a saved groove that is not selected for live playback
- **THEN** the library SHALL retain the edits and the current playback groove SHALL remain unchanged
