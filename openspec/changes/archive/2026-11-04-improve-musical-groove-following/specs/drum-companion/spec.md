# Spec Delta

## Purpose

The drum companion provides a live rhythm partner for solo performers, with groove, feel, and dynamics that remain musically intelligible as the performer changes phrasing, timing, and energy.

## ADDED Requirements

### Requirement: Feel controls audible timing and articulation
The system SHALL give tight and relaxed feels distinct, documented timing or articulation behavior; feel SHALL NOT be implemented solely by lowering density or removing core groove accents.

#### Scenario: Compare tight and relaxed feels
- **WHEN** a user switches feel while keeping style, phrase, and intensity unchanged
- **THEN** future unscheduled bars SHALL reflect the selected feel with bounded, repeatable timing or articulation differences while preserving the core groove

#### Scenario: Preserve the backbeat at relaxed feel
- **WHEN** a pattern has a defined backbeat and the user selects relaxed feel
- **THEN** the backbeat SHALL remain present unless the selected style or phrase explicitly omits it

### Requirement: Vary repeated bars without losing the pulse
During sustained playback, the system SHALL provide bounded, style-appropriate variation in accents or articulation while preserving the groove's underlying pulse and core pattern.

#### Scenario: Play a sustained groove
- **WHEN** the same style and phrase continue across multiple bars
- **THEN** at least some bars SHALL vary in documented accents, articulation, or ghost-note activity, and no variation SHALL displace the underlying pulse unpredictably

### Requirement: Intensity preserves core groove identity
The intensity control SHALL communicate accompaniment strength without unexpectedly removing essential kick or backbeat events at nonzero settings.

#### Scenario: Reduce intensity without losing the groove
- **WHEN** intensity is reduced from a nonzero setting to another nonzero setting
- **THEN** the core groove SHALL remain recognizable while its output strength or explicitly documented supplementary density changes

### Requirement: Follow tempo without unsupported pulse changes
When tempo evidence is ambiguous between plausible half-time or double-time interpretations, the system SHALL preserve its last stable pulse until evidence supports a change, without reporting an unsupported octave jump as a reliable tempo update.

#### Scenario: Ambiguous sparse pulse
- **WHEN** sparse or syncopated input supports multiple plausible pulse interpretations after a stable tempo has been established
- **THEN** the system SHALL retain the stable pulse and expose the current confidence without an unsupported half-time or double-time switch

#### Scenario: Consistent new pulse
- **WHEN** repeated onset evidence supports a different plausible pulse with sufficient confidence
- **THEN** the system SHALL adapt the tempo for future unscheduled bars without moving already scheduled events

### Requirement: Handle sparse input using the selected onset timeout
The system SHALL preserve the established groove through onset gaps shorter than the selected no-onset timeout and SHALL use the configured timeout to distinguish sparse playing from sustained musical inactivity.

#### Scenario: Sparse playing remains within timeout
- **WHEN** a performer plays sparse guitar or vocal phrases and a new onset arrives before the selected timeout expires
- **THEN** playback SHALL retain the stable tempo and groove without entering the inactivity transition

#### Scenario: No onset timeout expires
- **WHEN** no onset arrives before the configured timeout expires
- **THEN** the existing downbeat-aligned one-bar hold and one-bar fade SHALL begin without changing the reported raw tempo confidence

### Requirement: Recover from inactivity without disrupting phase
When activity resumes during the hold or fade, the system SHALL preserve the running bar phase, keep queued events at their original positions, and ramp gain back over one beat; an explicit stop SHALL remain immediate.

#### Scenario: Activity returns during fade
- **WHEN** onsets resume before the fade completes
- **THEN** the pending fade SHALL be cancelled and playback SHALL recover at the next downbeat without resetting phase or moving queued events

#### Scenario: User stops during a transition
- **WHEN** the user explicitly stops playback during hold or fade
- **THEN** playback SHALL stop immediately without waiting for a downbeat