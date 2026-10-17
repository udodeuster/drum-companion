# Design

## Context

See proposal.md - Why. This is a greenfield live accompaniment feature for a solo guitar + voice performance. The design needs to balance latency, musicality, and usability while focusing on the performer’s actual musical cues rather than a generic room-audio signal.

## Goals / Non-Goals

**Goals:**
- Detect rhythmic cues from solo guitar and vocal performance with low latency.
- Generate adaptive drum output that follows the artist's phrasing, pauses, and dynamics.
- Offer style controls and humanization while preserving a stable groove.
- Provide local browser controls from the host computer and a paired phone on the same private network.

**Non-Goals:**
- Full arrangement generation beyond drum accompaniment.
- Broad multi-instrument tracking for a full band or room mix.
- Real-time collaborative multitrack mixing.

## Decisions

- Target v1 specifically at solo guitar + voice performance, which keeps the analysis problem bounded and better aligned with the README’s intent.
- Use an audio-first analysis pipeline: input capture -> onset and tempo estimation -> phrase detection -> groove selection -> drum playback.
- Start with a hybrid rule-based plus pattern-library approach instead of a black-box model so behavior is explainable, testable, and tunable.
- Treat the groove as structured metadata with tempo, subdivision, swing, accent map, and variation profile rather than a single fixed pattern.
- Keep a user-facing "feel" control for tight vs. relaxed interpretation and separate presets for style (for example rock, folk, or indie).
- Render drum sounds through a sample-based engine or synthesized voices so attack, decay, and velocity changes stay natural.
- Serve the HTML control page and its API from the companion process; support loopback access on the host and private-network access for a phone, without a cloud dependency.
- Run capture/playback in a managed worker so browser requests can start, stop, inspect, and update the active session without blocking the web server.
- Require a one-time PIN displayed by the host app to pair a browser. Issue a session credential after pairing, reject unauthenticated control requests, and invalidate sessions when the app session ends.
- Apply mute and master-level updates immediately. Apply style, feel, phrase, and intensity to future unscheduled bars so already queued audio is not moved; require audio to stop before changing devices.

## Risks / Trade-offs

- [Detection errors] → Use confidence thresholds and fallback to the last stable tempo when the signal is ambiguous.
- [Latency vs. musicality] → Keep the analysis loop lightweight and prioritize a responsive low-latency path with a slightly lighter analysis in the highest-risk moments.
- [Mechanical repetition] → Add variation rules that adjust microtiming, accent placement, and ghost notes within a constrained style envelope.
- [Network access to microphone and playback controls] → Keep the service intended for a private LAN, require PIN pairing, reject unpaired requests, and do not expose it through router port forwarding. Plain HTTP on a trusted LAN does not protect against a hostile network observer.

## Migration Plan

- No migration is required; this is a greenfield feature introduced behind a feature flag or mode selector in the app.

## Open Questions

- Which primary input sources are in scope for v1: guitar, microphone input, MIDI, or all live audio sources?
