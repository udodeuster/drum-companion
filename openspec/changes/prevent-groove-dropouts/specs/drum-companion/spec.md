# Spec Delta

## Purpose

The drum companion provides a responsive live rhythm partner that preserves musical continuity through uncertain tempo measurements and brief performance pauses, while still fading after sustained inactivity.

## ADDED Requirements

### Requirement: Preserve the groove during tempo uncertainty
While live input remains active and musical onsets continue, the system SHALL retain the last stable tempo and groove when current tempo confidence is unreliable, without changing the reported confidence measurement. If no onset is detected within the configured timeout, the system SHALL treat the performance as musically inactive even if RMS energy remains above the signal-activity threshold.

#### Scenario: Confidence drops while the performer continues playing
- **WHEN** a tempo observation has low confidence or is marked discontinuous while active musical onsets continue and a stable groove has already been established
- **THEN** playback SHALL continue with the last stable tempo and groove, and the reported confidence SHALL reflect the current observation

#### Scenario: RMS remains active but musical onsets stop
- **WHEN** RMS energy remains active but no musical onset is detected for the configured number of bars
- **THEN** the system SHALL classify the performance as musically inactive and begin the bar-aligned hold and fade behavior while leaving raw tempo confidence unchanged

### Requirement: Configure the no-onset timeout
The user SHALL be able to configure how many bars without a detected onset classify an active signal as musically inactive, using the CLI at startup or the browser control page during playback.

#### Scenario: Default timeout
- **WHEN** the user does not set a no-onset timeout
- **THEN** the system SHALL use a default of one bar

#### Scenario: Choose a timeout
- **WHEN** the user sets the no-onset timeout from the CLI or browser control page
- **THEN** the system SHALL accept 0, 1, 2, or 4 bars and apply the selected value to the live session

### Requirement: Fade the groove only after sustained inactivity
When RMS inactivity or the configured no-onset timeout classifies the performance as inactive, the system SHALL begin its transition on the next downbeat, hold the last stable groove for one complete bar, and fade its intensity to silence over the following complete bar.

#### Scenario: Brief pause within the grace bar
- **WHEN** input becomes inactive between downbeats or an onset timeout expires before the next downbeat
- **THEN** playback SHALL continue the last stable groove without an abrupt mute until the next downbeat, then hold for one complete bar

#### Scenario: Inactivity persists beyond the grace bar
- **WHEN** input remains inactive for one complete bar after the aligned transition begins
- **THEN** playback intensity SHALL decrease progressively to silence over the following complete bar

#### Scenario: Input returns during the grace period or fade
- **WHEN** active input resumes before the fade completes
- **THEN** the pending fade SHALL be cancelled, playback SHALL resume on the next downbeat without resetting the current bar phase, gain SHALL ramp back over one beat, and already scheduled audio events SHALL remain at their original positions

#### Scenario: User explicitly stops playback
- **WHEN** the user requests stop during a grace period or fade
- **THEN** playback SHALL stop immediately without waiting for the bar transition