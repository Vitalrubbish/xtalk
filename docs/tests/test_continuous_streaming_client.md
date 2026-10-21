# Continuous streaming ASR tests

Verify 80 ms input hints, distinct pause/EOF requests and direct online transcript delivery.

The tests use deferred HTTP results with the real `ASRManager` and `MicroTurnAssembler`. They cover same-tick delivery without further audio, empty first and unchanged windows, exactly one read per tick with no independent polling, preservation of partial audio, no EOF from reads, and cleanup of in-flight reads on cancellation or shutdown.

With `acoustic_vad_enabled=false`, continuous ASR owns the session and the service disables acoustic VAD detection, speech-start/end control and pause/resume scheduling. The browser opens a VAD-free input device after the handshake; legacy acoustic signals are ignored at the gateway. Audio input remains continuous across silence and playback, and each micro-turn reads the current transcript without closing the decoder.
