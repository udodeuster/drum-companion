# Spec Delta

## Purpose

The audio-output capability renders the drum companion's generated groove as audible sampled drums through a selected Windows output device, with a small offline starter kit and responsive performer controls.

## ADDED Requirements

### Requirement: Provide a redistributable offline starter kit
The system SHALL include a usable starter kit containing kick, snare, closed hi-hat, open hi-hat, and cymbal one-shot sounds, with source and license information recorded for every bundled asset.

#### Scenario: First playback without a network connection
- **WHEN** the application is installed and the user starts a groove while offline
- **THEN** the bundled kit is available for playback without downloading additional samples

### Requirement: Select and open an audio output device
The system SHALL list available output devices and allow the user to select one for drum playback.

#### Scenario: Selected output device opens successfully
- **WHEN** the user starts playback on an available output device
- **THEN** the system opens that device and routes the generated drum audio to it

#### Scenario: Selected output device is unavailable
- **WHEN** the selected device cannot be opened or playback fails
- **THEN** the system reports an actionable error and does not claim playback is active

### Requirement: Render groove events at the current musical tempo
The system SHALL schedule bundled drum samples according to the generated groove, current tempo, and event velocity without shifting events that are already scheduled.

#### Scenario: Groove begins at a reliable tempo
- **WHEN** the user starts accompaniment with a reliable tempo and groove pattern
- **THEN** audible drum events follow the pattern at the supplied tempo and apply the pattern's accent and velocity differences

#### Scenario: Tempo changes during playback
- **WHEN** a new reliable tempo is received during playback
- **THEN** subsequent unscheduled events follow the updated tempo while events already scheduled retain their timing

### Requirement: Provide immediate playback controls
The system SHALL provide start, stop, master-level, and immediate-mute controls for sampled drum playback.

#### Scenario: Performer stops or mutes accompaniment
- **WHEN** the user activates stop or mute
- **THEN** no further drum sample is audible after the control takes effect

#### Scenario: Performer adjusts master level
- **WHEN** the user changes the master level during playback
- **THEN** subsequent output reflects the new level without changing the groove timing
