# Spec Delta

## Purpose

The groove library lets performers author and reuse named drum patterns while retaining the live tempo following and automatic groove mode of the companion.

## ADDED Requirements

### Requirement: Edit a multi-track sixteen-step groove
The system SHALL let users edit a groove as sixteen on/off steps for each of kick, snare, closed hi-hat, open hi-hat, and cymbal, with an independent track level from 0.0 to 1.0.

#### Scenario: Toggle an instrument step
- **WHEN** a user toggles a cell in an instrument track
- **THEN** only that instrument's event at that step SHALL be added or removed

#### Scenario: Adjust a track level
- **WHEN** a user changes an instrument's track level
- **THEN** playback SHALL change that instrument's level without changing other tracks or the master output level

### Requirement: Start a groove from blank or automatic accompaniment
The system SHALL let users create a groove with all steps off or copy the current automatic groove into an editable sixteen-step pattern.

#### Scenario: Create a blank groove
- **WHEN** a user creates a groove from the blank option
- **THEN** the editor SHALL show all five tracks with all sixteen steps off

#### Scenario: Copy the automatic groove
- **WHEN** a user creates a groove from the current automatic accompaniment
- **THEN** its existing eighth-note events SHALL appear on the corresponding even-numbered sixteenth steps and the intervening steps SHALL be off

### Requirement: Save named grooves persistently
The system SHALL save a user's named groove, including its step states and track levels, to persistent host-local storage only after explicit confirmation.

#### Scenario: Save a new groove
- **WHEN** a user enters a name and explicitly saves a valid groove
- **THEN** the groove SHALL appear in the saved library and remain available after the application restarts

#### Scenario: Preserve a saved groove while editing
- **WHEN** a user changes a saved groove without confirming save
- **THEN** the stored version SHALL remain unchanged and the editor SHALL indicate that there are unsaved changes

#### Scenario: Reject an invalid save
- **WHEN** a user attempts to save a groove with an empty or duplicate name
- **THEN** the system SHALL report the validation error and SHALL NOT replace or create a saved groove

### Requirement: Select automatic or saved groove playback
The system SHALL let users select Auto or a saved groove in the live control page; a selected saved groove SHALL retain live tempo and activity detection while its authored steps determine the drum events.

#### Scenario: Select a saved groove
- **WHEN** a user selects a saved groove and starts accompaniment
- **THEN** its enabled steps SHALL play at the detected tempo while the live activity behavior continues to operate

#### Scenario: Scale custom groove intensity
- **WHEN** the user changes the intensity setting while a saved groove is selected
- **THEN** the setting SHALL scale all enabled events together without changing the relative track levels

### Requirement: Apply feel timing to custom grooves
The system SHALL apply the selected feel to custom-groove timing, delaying eighth-note offbeats only when relaxed feel is selected.

#### Scenario: Play a custom groove with relaxed feel
- **WHEN** a custom groove is played with relaxed feel
- **THEN** eighth-note offbeats SHALL use the existing 55% swing timing and all other steps SHALL retain their authored grid positions

#### Scenario: Return to automatic accompaniment
- **WHEN** a user selects Auto
- **THEN** the existing automatically generated accompaniment behavior SHALL be used

### Requirement: Apply groove edits without moving scheduled events
The system SHALL apply saved-groove changes to future unscheduled bars without moving events that have already been scheduled.

#### Scenario: Edit a groove during playback
- **WHEN** a saved groove is changed and saved during playback
- **THEN** subsequent unscheduled bars SHALL use the saved changes while already scheduled events retain their timing

### Requirement: Preview an unsaved groove independently
The system SHALL let users start and stop a looping preview of the current editor draft through the host audio output without requiring microphone capture.

#### Scenario: Start preview without a live session
- **WHEN** the user starts preview while no live session is active
- **THEN** the current editor draft SHALL loop through the host audio output

#### Scenario: Stop preview
- **WHEN** the user stops the editor preview
- **THEN** preview playback SHALL stop and no further preview events SHALL be scheduled

### Requirement: Set the preview tempo
The system SHALL provide a manually adjustable preview tempo, initialized to the most recently detected live tempo when available and otherwise to 100 BPM.

#### Scenario: Preview without a previously detected tempo
- **WHEN** the user opens preview and no live tempo is available
- **THEN** the preview tempo SHALL default to 100 BPM and remain manually adjustable

#### Scenario: Preview with a previously detected tempo
- **WHEN** a live tempo is available from the most recent session
- **THEN** the preview tempo SHALL initialize from that value and remain manually adjustable

### Requirement: Apply draft edits during preview without saving
The system SHALL use unsaved editor changes for preview and apply changes made during a loop from the next bar without persisting them.

#### Scenario: Edit the draft while previewing
- **WHEN** the user changes a step or track level while preview is looping
- **THEN** the current bar SHALL retain its scheduled events and the next bar SHALL use the updated draft without saving it

### Requirement: Prevent preview from overlapping the live session
The system SHALL prevent editor preview from starting while a live session is active and SHALL explain that the user must stop the live session first.

#### Scenario: Start preview during live playback
- **WHEN** the user attempts to start preview while the live session is active
- **THEN** preview SHALL remain stopped and the editor SHALL explain that live playback must be stopped first
