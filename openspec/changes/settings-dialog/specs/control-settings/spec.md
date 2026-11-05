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

### Requirement: Choose editor tracks in Settings
The system SHALL let the user choose in Settings which drum instruments are shown in the main-page groove editor, SHALL keep at least one visible, and SHALL remember the choice on that device. Hiding a track SHALL NOT change the groove's steps, levels, or playback.

#### Scenario: Hide an instrument
- **WHEN** the user unchecks an instrument in Settings
- **THEN** its row disappears from the editor while its steps and playback are unchanged

#### Scenario: Last visible instrument
- **WHEN** only one instrument is visible
- **THEN** it cannot be hidden

#### Scenario: Choice is remembered
- **WHEN** the user reloads the page on the same device
- **THEN** the same instruments are shown

### Requirement: Show phone pairing in Settings
The system SHALL show the phone-pairing QR code, one-time PIN, and phone link in the Settings dialog when the page is opened on the host computer, and SHALL NOT show them in the live view or to other clients.

#### Scenario: Pairing details on the host
- **WHEN** the user opens Settings in the host browser
- **THEN** the dialog shows the current QR code, PIN, and phone link

#### Scenario: Pairing details unavailable
- **WHEN** Settings is opened in a non-host browser
- **THEN** the dialog does not show a phone-pairing section

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
