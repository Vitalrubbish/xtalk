# DuplexCascade 在线运行时

## 模型与协议依据

InterClarify 使用已发布的 DuplexCascade 权重，训练另议。[官方代码](https://github.com/sbintuitions/DuplexCascade/tree/42893024ca90c8de8ac3ed624467ebc123512ff8)固定为 `42893024ca90c8de8ac3ed624467ebc123512ff8`。输入使用 ChatML，结束标记 `<|im_end|>`，静默 `<|no voice|>`；五个控制 token 为 user is talking、user finish talking、user interruption、user backchannel、user is thinking（带 `<|...|>` 定界）。

## 调度、历史和播放

会话启动即开启唯一 0.6 秒 micro-turn 时钟。每拍先同步读取连续 ASR 已产出的最新累计文本，再消费新增后缀。空音频非 final 调用只读取已有服务结果，不提交静音，也不创建独立轮询任务。空窗及首词前均输入 no voice。生成串行执行；慢请求期间聚合最新输入，避免过时窗口排队。

历史同时保存 user 文本与模型服务返回的 assistant token ID，下一条 prompt 直接复现官方 token 序列。实测解码文本无法反推生成 ID，因此保留 ID。ASR 修订更新已发 user 前缀并递增版本，同时保留 assistant 历史与独立已播事实。

一个回答 ID 与 TTS 流跨多个 micro-turn。`finish talking` 打开“正在播报”窗口；普通文本继续回答；user backchannel 保持当前流，允许在同一 micro-turn 的 token 后继续回答文本。`thinking` 结束 TTS 文本输入，其后文本开启新的合成分段。适配器始终解码到 `<|im_end|>`，不截断模型流。

`user is talking` 与 `user interruption` 仅在“正在播报”窗口内停止未播音频，对齐官方 `tts_speaking_flag` 门控。停播会结束播放与合成分段；同一 micro-turn 的后续文本另起 response 与合成会话。送 TTS 的文本去掉 ASCII 句点，前端转写保留句点，对齐官方 `filter_period_for_tts`。`ResponseUpdate`/`ResponseFinish` 确认已播文本，`TTSStarted` 表示交付门打开。

当前 TTS 客户端为 `KokoroSegmented`：保留句界，首段等待 300ms、后续等待 1200ms，后续 finalization 不改写已安排播放的音频。KV 缓存按会话复用，在改写、取消或淘汰时安全失效。

## 注册与配置

`duplex_enabled=true` 时，`Service` 替换原生语义控制 manager，保留 ASR、TTS、响应协调和播放。`DefaultAgent`、VAD/TurnSense 的语义轮次控制与系统 backchannel 旁路关闭。`LLMAgentLoop` 启动连续 ASR，不依赖 VAD 端点。后端 VAD 可在静音 `vad_redemption_ms`（600ms）后释放 ASR 片段；它只作为 ASR 边界，绝不参与轮次判定。不配置该模型时 `VADManager` 自我禁用，边界只剩输入网关在音频流结束处的处理。当前范围为单用户；长期会话和模型上下文上限需远端验证。

~~~json
{"service_config": {"duplex_enabled": true, "duplex_model_url": "http://127.0.0.1:8006", "duplex_micro_turn_seconds": 0.6, "duplex_max_new_tokens": 64, "duplex_timeline_enabled": true, "duplex_kv_cache_enabled": true}}
~~~

## 源码与测试

- [micro_turn.py](../src/xtalk/duplex_control/micro_turn.zh.md)：前缀、版本与时钟。
- [runtime_adapter.py](../src/xtalk/duplex_control/runtime_adapter.zh.md)：协议与原生 TTS 执行。
- [model_client.py](../src/xtalk/duplex_control/model_client.zh.md)：raw ChatML HTTP 流。
- [service.py](../src/xtalk/duplex_control/service.zh.md)：单一执行路径注册。
- [protocol.py](../src/xtalk/duplex_control/protocol.zh.md)：实际 token 与增量解析。
- [state.py](../src/xtalk/duplex_control/state.zh.md)：不可变前缀快照。
- [test_duplex_runtime.py](../tests/test_duplex_runtime.zh.md)：行为门禁。

~~~bash
conda run -n interclarify-dev python -m unittest tests.test_duplex_runtime -v
~~~

本地模拟门禁不能证明官方权重的语义质量或音频质量。远端需记录 tokenizer/权重、真实音频、打断延迟、长会话和所选评测集；模型服务严格拒绝超长上下文，不静默截断。
