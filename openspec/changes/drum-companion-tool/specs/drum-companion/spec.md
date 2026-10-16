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
