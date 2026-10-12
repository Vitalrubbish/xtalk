# DuplexCascade A2/A3 online runtime

## Model and protocol provenance

The user selected existing released weights on 2026-10-12; training remains a later decision. [Official code](https://github.com/sbintuitions/DuplexCascade/tree/42893024ca90c8de8ac3ed624467ebc123512ff8) is pinned to 42893024ca90c8de8ac3ed624467ebc123512ff8. Inputs use ChatML with <|im_end|> and <|no voice|>. The five controls are user is talking, user finish talking, user interruption, user backchannel and user is thinking, enclosed in <|...|>. Paper-format A1 APIs remain; online execution uses released tokenizer markers.

## Scheduling, history, and playback

After first nonblank ASR text, wait one 0.6-second interval and consume the cumulative-prefix delta. partial/pause/final update input; the clock invokes the model. Silent windows still contain no voice. Generation is serial; slow requests accumulate the latest input without obsolete queued windows. Assistant history retains raw output; answer continuations may contain plain text and budget truncation retains the length reason. ASR rewrites repair emitted user prefixes with incremented versions while preserving assistant history and separate heard facts; this adapts the official Word stream to cumulative ASR.

One answer ID and TTS stream span multiple micro-turns. finish talking starts an answer, ordinary text continues it and user backchannel retains it and may precede continuation text in the same micro-turn. thinking closes TTS text input. A complete <|user interruption|> immediately terminates the current system micro-turn: the adapter stops unplayed audio, closes the active DuplexCascade request and does not wait for <|im_end|>. It records the raw marker and adds an internal ChatML end marker only when retaining the turn in prompt history. The official demo also stops ongoing output on user is talking, and execution follows it. ResponseUpdate/ResponseFinish confirm heard text; TTSStarted opens delivery.

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

## Validation results (2026-10-12)

Local X-Talk discovery: 138 tests (135 PASS, 3 skipped); A2/A3 behavioral gate: 16/16. The interruption regression now verifies that a complete <|user interruption|> marker closes the model stream and micro-turn without waiting for <|im_end|>. Remote released-weight runtime smoke used source snapshot 17fd22d55cc7, verified 160 source files, completed 12 system micro-turns with zero errors and PASS status. Published weights use Qwen2 slow tokenizer for legacy fast-format compatibility and BF16; q/v base keys are explicitly migrated before strict loading. Scripted ASR prefixes and synthetic PCM do not establish real ASR/MOSS, audio quality, long-session or FDB acceptance.
