# Design

## Context

See proposal.md - Why and specs/drum-companion/spec.md. The current groove generator emits fixed eight-step patterns; feel and intensity affect note inclusion, while scheduled events use a stable bar clock and are not moved after issuance. The existing inactivity transition and frame-based gain envelope already provide phase-preserving hold, fade, and recovery behavior that this change should retain.

## Goals / Non-Goals

**Goals:**
- Separate core groove events from optional density, accent, and articulation changes.
- Make feel a deterministic, bounded musical treatment that can be tested independently of output level.
- Guard tempo updates against unsupported half-time/double-time switches while allowing sustained evidence to move the pulse.
- Validate behavior on representative sparse guitar-and-voice material as well as synthetic timing fixtures.

**Non-Goals:**
- Add automatic song-form recognition, new meter support, or new user controls in this change.
- Change the no-onset timeout choices or the established hold/fade/recovery schedule without listening evidence.
- Claim musical realism based only on synthetic test results.

## Decisions

- **Keep core events distinct from embellishments.** Represent the defining kick/backbeat pattern separately from optional notes, fills, and articulation. Apply nonzero intensity changes to output strength first; let any density change affect supplementary events, not silently erase the groove's identity. This is preferable to continuing threshold-based removal of core events, which makes small intensity changes alter the arrangement abruptly.
- **Use bounded, reproducible variation.** Select variation from style/feel rules and bar position so repeated playback is not mechanically identical while tests and sessions remain reproducible. Relaxed rock and folk add velocity-0.14 ghost snares on eighth-note steps 1 and 5 during bars 2 and 4 of each four-bar phrase; indie adds no ghost snares. Timing offsets cannot reorder events, cross a bar boundary, or alter the underlying pulse.
- **Treat feel as timing/articulation, not volume.** Keep tight feel on the intended grid. The musician-selected relaxed feel delays offbeat eighths by 0.05 beat (31.25 ms at 96 BPM); this is a 55% swing ratio. Do not add a swing slider unless listening shows that the existing choices cannot cover the intended use.
- **Add hysteresis to pulse changes.** Retain the last stable tempo for near-octave candidates (tempo ratios 0.46-0.54 or 1.85-2.15) until three consecutive reliable estimates agree within 5%. Other reliable changes remain responsive and apply only to unscheduled bars. This favors stability over a fast but musically surprising octave jump.
- **Preserve the transport and inactivity design.** Keep the existing downbeat-aligned hold/fade, one-beat recovery ramp, queued-event positions, and immediate stop contract. Validate these alongside sparse-input behavior; record any perceived pickup-response issue for a separate proposal rather than changing recovery timing here.
- **Use existing controls as the first interface.** Clarify feel and intensity semantics in the browser/CLI documentation. Add a control only if musician review identifies a distinct decision that cannot be expressed by style, feel, phrase, intensity, or timeout.

## Risks / Trade-offs

- [Relaxed timing can sound sloppy or style-inappropriate] → Tune bounded timing/articulation per style using musician listening sessions; retain tight as the default.
- [Protecting core events can make low intensity feel too busy] → Reduce their velocity and reserve density reduction for explicitly supplementary parts; test at low but nonzero settings.
- [Hysteresis can delay a legitimate tempo change] → Measure response on steady tempo-shift fixtures and real performances; prefer a short consistent-evidence window over a single uncertain estimate.
- [Sparse input may still be mistaken for inactivity] → Test guitar-only, vocal-only, and sparse phrase material against all timeout choices; keep the timeout visible and user-adjustable.
- [Musical quality is subjective] → Treat automated tests as timing/state guarantees and record musician listening outcomes separately; do not use passing synthetic tests as a quality verdict. Use the listening session to choose timing and ghost-note bounds before they become defaults.

## Migration Plan

No data migration or audio-device lifecycle change is expected. Keep the existing tight feel, style defaults, timeout values, and transition timing as compatibility anchors. Roll back groove-generation or tempo-hysteresis changes independently if listening reveals a loss of pulse or if regression fixtures show unstable scheduling.

