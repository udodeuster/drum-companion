# Proposal

## Why

The current accompaniment is mechanically predictable but does not yet deliver the promised relaxed feel, human variation, or reliable interpretation of sparse playing. A drummer-facing pass should make those musical behaviors explicit and test them against realistic guitar-and-voice performances without sacrificing the existing phase-stable pause and recovery behavior.

## What Changes

- Define tight and relaxed feel in terms of audible timing and articulation, rather than note removal or density alone.
- Add bounded, style-appropriate variation across repeated bars while preserving the underlying pulse and core groove.
- Make intensity behavior explicit so changes in loudness do not unexpectedly remove essential backbeat elements.
- Specify stable handling of plausible half-time and double-time interpretations and validate it with representative sparse input.
- Retain the existing configurable no-onset timeout and downbeat-aligned hold/fade/recovery contract, with focused musical acceptance scenarios.
- Defer changes to recovery timing, automatic phrase inference, and broader meter support until listening tests show a concrete need.

## Capabilities

### New Capabilities

- `drum-companion`: Live rhythmic accompaniment with musically distinct feel, bounded variation, and predictable response to sparse performance input.

### Modified Capabilities

None. The OpenSpec inventory currently contains no canonical capability specs; this change introduces the behavior contract using the project's established `drum-companion` path.

## Impact

- Likely affected code: `drum_companion/audio/groove.py`, `drum_companion/audio/analysis.py`, scheduler/output integration, browser and CLI settings if new controls are justified.
- Tests should cover pattern timing/articulation, intensity and backbeat continuity, sparse input, tempo ambiguity, and existing pause/recovery timelines.
- No dependency or audio-device lifecycle change is assumed. Human listening with representative guitar-and-voice material is required to judge swing, ghost-note audibility, phrase transitions, and recovery feel; synthetic fixtures alone cannot establish musical quality.