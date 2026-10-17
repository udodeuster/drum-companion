# Spec Delta

## Purpose

The drum companion capability provides a solo musician with a live rhythm partner that follows the performance and keeps the groove natural.

## ADDED Requirements

### Requirement: Follow the lead instrument in real time
The system shall listen to the active instrument and estimate tempo, phrase boundaries, and emphasis from the live performance.

#### Scenario: Guitar phrase with tempo shifts
- **WHEN** the musician plays a phrase with small tempo changes and accents
- **THEN** the system shall update the drum pattern timing and emphasis to align with the detected musical structure without locking to a rigid metronome

### Requirement: Select an appropriate drum feel
The system shall choose drum patterns, dynamics, and articulation based on the performance style and musical context.

#### Scenario: Different song intensity
- **WHEN** the performer shifts from a sparse verse to a more energetic chorus
- **THEN** the system shall move from restrained groove elements to fuller, more active drum arrangements while preserving natural swing and phrasing

### Requirement: Preserve musical realism
The system shall add timing variation, ghost notes, and accent patterns that feel human rather than robotic.

#### Scenario: Sustained performance
- **WHEN** the rhythm is playing for several bars
- **THEN** the system shall vary the pattern within the selected style to avoid mechanical repetition while maintaining the underlying pulse

### Requirement: Provide user control over accompaniment
The user shall be able to choose rhythm style, dynamic level, and whether the companion follows a loose or tight interpretation of the lead performance.

#### Scenario: User adjusts the feel
- **WHEN** the artist chooses a more relaxed or tighter groove
- **THEN** the system shall regenerate the accompaniment to match the selected intensity without breaking timing continuity

### Requirement: Control the live companion from a local browser
The system shall provide a browser control page on the host computer and allow paired devices on the same private network to control the live companion.

#### Scenario: Open controls on the host computer
- **WHEN** the user opens the local control page on the computer running the companion
- **THEN** the page shall show the live state and provide controls to start and stop capture and playback

#### Scenario: Pair a phone on the private network
- **WHEN** the user enters the one-time pairing PIN shown by the running app
- **THEN** the browser shall be authorized to view status and control the companion for that app session

#### Scenario: Reject an unpaired control request
- **WHEN** a browser sends a control request without a valid paired session
- **THEN** the system shall reject the request without starting, stopping, or changing the companion

### Requirement: Apply supported parameter changes during playback
The system shall allow supported accompaniment settings to be changed while live playback is active without moving audio events that have already been scheduled.

#### Scenario: Change output level or mute during playback
- **WHEN** the user changes the master level or mute state
- **THEN** the new value shall affect audio output immediately without resetting the playback timeline

#### Scenario: Change groove settings during playback
- **WHEN** the user changes style, feel, phrase, or intensity
- **THEN** the system shall use the new settings for future unscheduled bars while leaving already scheduled events unchanged

#### Scenario: Change an audio device during playback
- **WHEN** the user selects a different input or output device while audio is active
- **THEN** the system shall indicate that the change requires stopping and restarting audio
