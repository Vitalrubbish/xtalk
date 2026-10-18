# test_duplex_runtime.py

## Purpose, classes, and core methods

WireMicroTurnParser and DuplexRuntimeTests cover arbitrary marker splits, control semantics, continuation, token-budget termination, first-text clock start, silence, deltas, final deduplication, slow inference, rewrites, heard facts on interruption, errors, shutdown cancellation, stale-version rejection, native TTS/playback settlement, the single service control path and the ASR segment boundaries (one pause per acoustic speech end, resume on speech start, no pause for synthetic text input or before the consumer started). Uses a real EventBus and deterministic model service.

~~~bash
conda run -n paratalker-dev env PYTHONPATH=src python -m unittest tests.test_duplex_runtime -v
~~~

The interruption regression confirms that a marker resets unplayed audio only while the speaking window is open, that the model stream is still decoded to <|im_end|>, that generated assistant ids travel verbatim into the next prompt, and that a marker arriving before the window opens leaves playback untouched. The protocol observation keeps the raw marker. History stores user text plus assistant token ids, and `_request_history` builds the wire structure.

Adds user backchannel plus same-micro-turn continuation, including fragmented markers and one response/TTS stream. Waiting controls still reject missing EOS during an active answer.

ScriptedClient appends a synthetic stop record when a script omits `GenerationEnd`, matching a real service that always reports generated ids.


Issue001c：移除同前缀重复回答的语义拦截，允许模型thinking后在相同前缀再次接话，逐拍完整保存原始生成IDs；重复内容由评测判质量失败。重复request_id和过期版本仍拒绝，输出仍经唯一播放协调器。新增回归验证两次不同response_id及完整assistant历史。
