# audio-analysis Specification

## Purpose

The audio-analysis capability converts a solo performer’s mixed microphone signal into confidence-aware rhythmic and dynamic cues that a drum companion can use during live performance.

## Requirements

### Requirement: Capture a live microphone signal
The system SHALL allow the user to select an available microphone input and start or stop live analysis of a mixed guitar-and-voice signal.

#### Scenario: Start analysis with an available device
- **WHEN** the user selects an available input and starts analysis
- **THEN** the system captures audio and begins producing analysis updates without requiring a manually entered tempo

#### Scenario: Input device is unavailable
- **WHEN** the selected device cannot be opened or capture fails
- **THEN** the system reports an actionable error and does not present stale or fabricated measurements as live results

### Requirement: Estimate rhythmic cues from captured audio
The system SHALL produce timestamped onset events and an evolving tempo estimate from the live signal, with a confidence value for each estimate.

#### Scenario: Performer plays a steady guitar rhythm
- **WHEN** the captured signal contains repeated guitar attacks at a stable pulse
- **THEN** analysis updates report onset timing and a tempo estimate that converges on the performed pulse

#### Scenario: Performer changes tempo
- **WHEN** the performed pulse changes over time
- **THEN** subsequent analysis updates adapt the tempo estimate while preserving the timing of previously emitted onset events

### Requirement: Report overall performance dynamics
The system SHALL report a normalized overall signal-energy value for the mixed microphone input and SHALL NOT represent that value as separate guitar or vocal energy.

#### Scenario: Guitar and voice are captured together
- **WHEN** the microphone captures both guitar and voice
- **THEN** the analysis result reports their combined signal energy without claiming to identify each source independently

### Requirement: Signal uncertainty and silence are explicit
The system SHALL distinguish low-confidence or silent input from a reliable rhythmic estimate and expose confidence to downstream accompaniment behavior.

#### Scenario: Performer pauses or the signal is ambiguous
- **WHEN** the input contains silence, noise, or an irregular passage that prevents a reliable estimate
- **THEN** the system marks affected estimates as low confidence and the drum companion can retain its last stable pulse or reduce activity

### Requirement: Keep live audio private by default
The system SHALL process live microphone audio in memory and SHALL NOT save a recording unless the user explicitly requests a recording feature.

#### Scenario: Live analysis session ends
- **WHEN** the user stops analysis
- **THEN** capture ends and the system has not persisted the live audio as a recording

### Requirement: Support repeatable analysis validation
The analysis pipeline SHALL accept recorded audio fixtures through a non-live test path so onset, tempo, dynamics, and uncertainty behavior can be validated reproducibly.

#### Scenario: Analyze a known test recording
- **WHEN** a test fixture with known rhythmic events is processed through the analysis path
- **THEN** the test can compare emitted onset and tempo results against its expected values without microphone hardware
