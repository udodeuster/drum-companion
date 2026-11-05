# Spec Delta

## Purpose

Provides a dedicated, readily accessible place for device and playback configuration while keeping live performance controls focused on the main view.

## ADDED Requirements

### Requirement: Open settings from the live view
The system SHALL provide a gear-icon control on the live view that opens a Settings dialog.

#### Scenario: Open settings
- **WHEN** the user activates the gear icon
- **THEN** the Settings dialog opens without navigating away from the live view

### Requirement: Keep audio device controls in Settings
The system SHALL provide microphone selection, drum output selection, and drum playback enablement in the Settings dialog instead of the live view.

#### Scenario: Configure audio devices
- **WHEN** the user opens Settings
- **THEN** the Audio Devices controls are available in the dialog and are absent from the live view

### Requirement: Preserve live controls outside Settings
The system SHALL keep performance status, groove controls, and Start/Stop controls available on the live view independently of the Settings dialog.

#### Scenario: Return to live controls
- **WHEN** the user closes the Settings dialog
- **THEN** the live view remains available with its performance, groove, and transport controls

### Requirement: Explain device changes during live playback
The system SHALL explain that audio device and playback-mode changes require stopping the live session and SHALL keep the transport available outside the Settings dialog.

#### Scenario: Settings opened during a live session
- **WHEN** the user opens Settings while the live session is running
- **THEN** the dialog explains that the user must close it to stop the session before changing devices or playback mode
