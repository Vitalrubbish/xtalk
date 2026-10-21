# DuplexCascade online runtime

## Model and protocol provenance

InterClarify uses the released DuplexCascade weights; training is a separate decision. The [official code](https://github.com/sbintuitions/DuplexCascade/tree/42893024ca90c8de8ac3ed624467ebc123512ff8) is pinned to `42893024ca90c8de8ac3ed624467ebc123512ff8`. Inputs use ChatML with `<|im_end|>` and `<|no voice|>`. The five controls are user is talking, user finish talking, user interruption, user backchannel and user is thinking, enclosed in `<|...|>`.

## Scheduling, history, and playback

A single 0.6-second micro-turn clock starts with the session. Each tick reads the latest completed continuous-ASR result before consuming its cumulative-prefix delta. Empty non-final reads only fetch existing service output, submit no silence and create no polling task. Silent windows, including those before the first recognized word, contain no voice. Generation is serial; slow requests accumulate the latest input without obsolete queued windows.

History stores user text together with the exact assistant token IDs returned by the model service, so every prompt reproduces the released token run. Decoded text cannot round-trip back into generated IDs, which is why IDs are retained. ASR revisions update delivered user prefixes with incremented versions while preserving assistant history and separate heard facts.

One answer ID and TTS stream span multiple micro-turns. `finish talking` opens the speaking window; ordinary text continues the answer; user backchannel retains the current stream and may precede continuation text in the same micro-turn. `thinking` closes TTS text input, and later text starts a new synthesis segment. The adapter always decodes to `<|im_end|>` and never truncates the model stream.

`user is talking` and `user interruption` reset unplayed audio only while the speaking window is open, mirroring the released `tts_speaking_flag` gate. A reset stops playback and the synthesis segment; later text in the same micro-turn opens a new response and synthesis session. Text sent to TTS drops ASCII periods while the frontend transcript keeps them, matching the released `filter_period_for_tts`. `ResponseUpdate`/`ResponseFinish` confirm heard text; `TTSStarted` opens delivery.

The current TTS client is `KokoroSegmented`: it preserves sentence boundaries, uses a 300 ms first-segment wait and 1200 ms continuation wait, and never lets a later finalization rewrite audio already scheduled for playback. KV reuse is session-scoped and invalidated on rewrite, cancellation or eviction.

## Registration and configuration

With `duplex_enabled=true`, `Service` replaces native semantic managers and retains ASR, TTS, coordinator and playback. `DefaultAgent`, VAD/TurnSense semantic turn control and system backchannel paths are disabled. `LLMAgentLoop` starts continuous ASR without VAD endpointing. A backend VAD may release the ASR segment after `vad_redemption_ms` (600 ms) of silence; it is only an ASR boundary, never a turn decision. Without that model `VADManager` disables itself and the only boundary is the input gateway at the end of the audio stream. The current scope is one user; long sessions and model context limits require remote validation.

~~~json
{"service_config": {"duplex_enabled": true, "duplex_model_url": "http://127.0.0.1:8006", "duplex_micro_turn_seconds": 0.6, "duplex_max_new_tokens": 64, "duplex_timeline_enabled": true, "duplex_kv_cache_enabled": true}}
~~~

## Source and tests

- [micro_turn.py](../src/xtalk/duplex_control/micro_turn.md): prefixes, versions and clock.
- [runtime_adapter.py](../src/xtalk/duplex_control/runtime_adapter.md): protocol and native TTS execution.
- [model_client.py](../src/xtalk/duplex_control/model_client.md): raw ChatML HTTP stream.
- [service.py](../src/xtalk/duplex_control/service.md): single execution path registration.
- [protocol.py](../src/xtalk/duplex_control/protocol.md): wire tokens and incremental parser.
- [state.py](../src/xtalk/duplex_control/state.md): immutable prefix snapshots.
- [test_duplex_runtime.py](../tests/test_duplex_runtime.md): behavioral gate.

~~~bash
conda run -n interclarify-dev python -m unittest tests.test_duplex_runtime -v
~~~

Local simulation does not establish released-weight semantic quality or audio quality. Remote evidence must record tokenizer/weights, real audio, interruption latency, long sessions and the selected evaluation set. The model service rejects excessive context instead of silently truncating it.
