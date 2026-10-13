# DuplexCascade A2/A3 online runtime

## Model and protocol provenance

The user selected existing released weights on 2026-10-12; training remains a later decision. [Official code](https://github.com/sbintuitions/DuplexCascade/tree/42893024ca90c8de8ac3ed624467ebc123512ff8) is pinned to 42893024ca90c8de8ac3ed624467ebc123512ff8. Inputs use ChatML with <|im_end|> and <|no voice|>. The five controls are user is talking, user finish talking, user interruption, user backchannel and user is thinking, enclosed in <|...|>. Paper-format A1 APIs remain; online execution uses released tokenizer markers.

## Scheduling, history, and playback

After first nonblank ASR text, wait one 0.6-second interval and consume the cumulative-prefix delta. partial/pause/final update input; the clock invokes the model. Silent windows still contain no voice. Generation is serial; slow requests accumulate the latest input without obsolete queued windows. History stores user text together with the exact assistant token ids returned by the service, so every prompt reproduces the released token run. Decoded text cannot round-trip back into generated ids (measured 52% mismatch on sampled id runs), which is why ids are retained. ASR rewrites repair emitted user prefixes with incremented versions while preserving assistant history and separate heard facts; this adapts the official Word stream to cumulative ASR.

One answer ID and TTS stream span multiple micro-turns. finish talking opens the speaking window, ordinary text continues the answer and user backchannel retains it and may precede continuation text in the same micro-turn. thinking closes TTS text input, and later text starts a fresh synthesis session because the MOSS client finalizes a stream when flushed. The adapter always decodes to <|im_end|> and never truncates the model stream. user is talking and user interruption reset unplayed audio only while the speaking window is open, mirroring the released tts_speaking_flag gate. A reset stops playback and the synthesis session, and later text in the same micro-turn opens a new response and session, which matches the released server reconnecting TTS after its reset. Text sent to TTS drops ASCII periods while the frontend transcript keeps them, matching the released filter_period_for_tts. ResponseUpdate/ResponseFinish confirm heard text; TTSStarted opens delivery.

## Registration and configuration

With duplex_enabled=true, Service replaces native semantic managers and retains ASR/TTS/coordinator/playback. DefaultAgent, VAD/TurnSense semantic control and system backchannel paths are disabled. LLMAgentLoop starts continuous ASR without VAD endpointing. The current scope is one user; long sessions and model context limits require remote validation.

~~~json
{"service_config": {"duplex_enabled": true, "duplex_model_url": "http://127.0.0.1:8006", "duplex_micro_turn_seconds": 0.6, "duplex_max_new_tokens": 64, "duplex_timeline_enabled": true}}
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
conda run -n paratalker-dev env PYTHONPATH=src python -m unittest tests.test_duplex_runtime -v
~~~

Local simulation does not establish released-weight semantic quality or A4 acceptance. Remote evidence must record tokenizer/weights, real audio, interruption latency, long sessions and FDB. The model service rejects excessive context instead of silently truncating it.

## Validation results (2026-10-13)

X-Talk suite: 142 tests (139 PASS, 3 skipped); A2/A3 behavioral gate: 34/34. The interruption regression verifies that a marker resets unplayed audio only inside the speaking window while the stream is still decoded to <|im_end|>, and that assistant ids travel verbatim into the next prompt. Remote released-weight smoke from 2026-10-12 used snapshot 17fd22d55cc7, verified 160 source files and completed 12 system micro-turns with zero errors. Published weights load with the fast Qwen2 tokenizer and BF16; q/v base keys are explicitly migrated before strict loading. Scripted ASR prefixes and synthetic PCM do not establish real ASR/MOSS, audio quality, long-session or FDB acceptance.
