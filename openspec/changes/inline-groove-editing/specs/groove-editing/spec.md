# Spec Delta

## Purpose

Allows users to edit drum tracks directly in the groove controls and to persist their changes as saved grooves without changing Auto's dynamic generation.

## ADDED Requirements

### Requirement: Edit drum tracks inline
The system SHALL display editable drum-step tracks for the current groove in the Groove section without requiring a separate editor to be opened.

#### Scenario: Edit a selected saved groove
- **WHEN** a saved groove is selected for playback
- **THEN** its drum-step tracks and levels are available for direct editing in the Groove section

### Requirement: Edit Auto as a snapshot
The system SHALL create an editable snapshot of the current Auto pattern when the user edits tracks while Auto is selected, without changing Auto's dynamic generation.

#### Scenario: Edit tracks while Auto is selected
- **WHEN** the user changes a drum track while Auto is selected
- **THEN** the change applies to the live output on future bars through an editable snapshot while Auto remains dynamically generated and unchanged

### Requirement: Save changes to the selected groove
The system SHALL allow users to save edits to a selected saved groove while retaining that groove's identity.

#### Scenario: Update a saved groove
- **WHEN** the user edits a saved groove and chooses to save changes to it
- **THEN** the saved groove is updated with the edited tracks and levels under its existing identity

### Requirement: Save edits as a new groove
The system SHALL allow users to save an edited groove as a separately named groove without replacing its source.

#### Scenario: Save a saved-groove edit as a copy
- **WHEN** the user edits a saved groove and chooses to save it under a new name
- **THEN** a new saved groove is created and the original remains unchanged

#### Scenario: Save an Auto snapshot
- **WHEN** the user chooses to save an edited Auto snapshot and supplies a name
- **THEN** a new saved groove is created and Auto remains unchanged
