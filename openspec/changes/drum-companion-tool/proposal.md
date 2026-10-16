# Proposal

## Why

The drum companion tool addresses a gap for solo artists who need a natural backing rhythm that follows live performance without requiring a full band. It should react to musical phrases, timing variations, and dynamic shifts so the groove feels organic rather than metronomic.

## What Changes

- Add a new `drum-companion` capability for live solo performances involving guitar and voice.
- Detect the lead performer’s timing, phrasing, accents, and dynamic shifts in real time without requiring a fixed metronome.
- Generate a matching drum pattern, feel, and variation that adapts to song sections, vocal pacing, and performance energy.
- Expose playback controls for style selection, humanization, and dynamic response so the groove remains musical.
- Keep the first release limited to solo guitar + voice accompaniment rather than generic multi-instrument or full-band analysis.

## Capabilities

### New Capabilities

- `drum-companion`: real-time rhythm accompaniment that listens to a solo performer and produces adaptive, natural-sounding drum patterns.

### Modified Capabilities

- None

## Impact

- New live-audio analysis and rhythm generation workflow.
- Likely integration with the app’s audio engine, transport controls, and UI.
- Added dependency on real-time audio processing and drum sample or synthesis libraries.
