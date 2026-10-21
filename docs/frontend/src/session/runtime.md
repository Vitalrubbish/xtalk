# runtime.ts

This module owns the frontend session handshake, continuous audio input and playback callbacks. The core session lifecycle stays unchanged; the client disables acoustic detection and signals according to server capability.

When the server reports `acoustic_vad_enabled=false` for continuous ASR, the client disables acoustic VAD detection, speech-start/end control and pause/resume scheduling. Session-level continuous PCM and per-micro-turn transcript reads are retained. After the handshake the browser opens a VAD-free input device; legacy acoustic signals are ignored at the gateway.

Verification covers residual VAD signals not triggering ASR control, continuous input during silence and playback, the same decoder session, and the negotiated handshake capability.
