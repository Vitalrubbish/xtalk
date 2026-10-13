# DuplexCascade A2/A3 在线运行时

## 模型与协议依据

根据用户 2026-10-12 决定，先使用已有官方训练权重，训练后续另议。[官方代码](https://github.com/sbintuitions/DuplexCascade/tree/42893024ca90c8de8ac3ed624467ebc123512ff8)固定为 42893024ca90c8de8ac3ed624467ebc123512ff8。实际输入为 ChatML，结束标记 <|im_end|>，静默 <|no voice|>；五个控制 token 为 user is talking、user finish talking、user interruption、user backchannel、user is thinking（带 <|...|> 定界）。论文式 A1 API 保留，线上使用官方 token。

## 调度、历史和播放

首次非空 ASR 后等待一个 0.6 秒窗口，消费累计前缀的新增后缀。partial/pause/final 更新输入，时钟调用 LLM；空窗仍输入 no voice。串行生成，慢请求期间聚合最新文本，避免过时窗口排队。历史同时保存 user 文本与模型服务返回的 assistant token id，下一条 prompt 直接复现官方 token 序列；实测解码文本无法反推生成 id（随机序列约 52% 不一致），因此保留 id。ASR 修订更新已发 user 前缀，版本递增，保留 assistant 历史与独立已播事实，这是对官方 Word 流的累计前缀适配。

一个回答 ID 与 TTS 流跨多个 micro-turn。finish talking 打开"正在播报"窗口，普通文本继续回答，user backchannel 保持当前流，允许同一 micro-turn 在 token 后继续回答文本。thinking 结束 TTS 文本输入，其后文本开启新的合成会话，因为 MOSS 客户端在 flush 后即终结该流。适配器始终解码到 <|im_end|>，不截断模型流。user is talking 与 user interruption 仅在"正在播报"窗口内停止未播音频，对齐官方 tts_speaking_flag 门控；停播会结束播放与合成会话，同一 micro-turn 的后续文本另起 response 与会话，与官方 reset 后重连 TTS 的行为一致。送 TTS 的文本去掉 ASCII 句点，前端转写保留句点，对齐官方 filter_period_for_tts。只有 ResponseUpdate/ResponseFinish 确认已播文本，TTSStarted 表示交付门已打开。

## 注册与配置

Service 在 duplex_enabled=true 时替换原生语义控制 manager，保留 ASR/TTS/coordinator/playback，关闭 DefaultAgent、VAD/TurnSense 与系统附和语义旁路。LLMAgentLoop 启动持续 ASR；窗口不依赖 VAD 端点。当前范围为单用户，长期会话和模型上下文上限需远端验证。

~~~json
{"service_config": {"duplex_enabled": true, "duplex_model_url": "http://127.0.0.1:8006", "duplex_micro_turn_seconds": 0.6, "duplex_max_new_tokens": 64, "duplex_timeline_enabled": true}}
~~~

## 源码与测试

- [micro_turn.py](../src/xtalk/duplex_control/micro_turn.zh.md)：前缀、版本与时钟。
- [runtime_adapter.py](../src/xtalk/duplex_control/runtime_adapter.zh.md)：协议与原生 TTS 执行。
- [model_client.py](../src/xtalk/duplex_control/model_client.zh.md)：raw ChatML HTTP 流。
- [service.py](../src/xtalk/duplex_control/service.zh.md)：单一执行路径注册。
- [protocol.py](../src/xtalk/duplex_control/protocol.zh.md)：实际 token 和增量解析。
- [state.py](../src/xtalk/duplex_control/state.zh.md)：不可变前缀快照。
- [test_duplex_runtime.py](../tests/test_duplex_runtime.zh.md)：行为门禁。

~~~bash
conda run -n paratalker-dev env PYTHONPATH=src python -m unittest tests.test_duplex_runtime -v
~~~

本地模拟门禁不能证明官方权重的语义质量或 A4 通过。远端需记录 tokenizer/权重、真实音频、打断延迟、长会话与 FDB；模型服务严格拒绝超长上下文，不静默截断。

## 验证结果（2026-10-13）

X-Talk 全量 142 项（139 PASS、3 skipped），A2/A3 行为门禁 34/34。interruption 回归确认：marker 仅在"正在播报"窗口内停止未播音频，模型流仍解码到 <|im_end|>，assistant id 原样进入下一条 prompt。远端官方权重冒烟沿用 2026-10-12 的 source snapshot=17fd22d55cc7、160 源文件校验通过、12 系统 micro-turn、errors=0。模型使用发布权重、fast Qwen2 tokenizer 与 BF16，q/v 基础权重键显式迁移后严格装载。脚本 ASR 前缀与模拟 PCM 不替代真实 ASR/MOSS、音频质量、长会话或 FDB。
