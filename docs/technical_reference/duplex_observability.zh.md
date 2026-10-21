# DuplexCascade 协议与可观测性

Duplex 运行时提供完整输出协议解析、原始成功/错误事件、请求与响应关联字段传递、JSONL 时间线和 TTSStarted 交付边界。LLM/TTS/播放复用原生 manager；在线路径见 [Duplex 运行时](duplex_runtime.zh.md)。

## 配置与日志

~~~json
{
  "service_config": {
    "duplex_timeline_enabled": true,
    "duplex_timeline_dir": "data/duplex_timeline",
    "duplex_timeline_history": 1000
  }
}
~~~

开关严格使用布尔 true；实时会话创建 session_id.jsonl。内存记录有界，文件追加并逐事件同步 flush；重新创建记录器时序号从 1 开始。sequence 表示记录顺序，monotonic_timestamp 表示事件创建时间；嵌套事件可能先记录。空 ID 保持原值，客户端播放回执可以只带 response_id，离线分析按显式 ID 连接事件。已播文本由 ResponseUpdate/ResponseFinish 确认；TTSStarted 表示交付门打开，不能证明用户已经听到音频。

## 文件映射

| 实现文件 | 镜像说明 |
| --- | --- |
| src/xtalk/duplex_control/__init__.py | [__init__](../src/xtalk/duplex_control/__init__.zh.md) |
| src/xtalk/duplex_control/protocol.py | [protocol](../src/xtalk/duplex_control/protocol.zh.md) |
| src/xtalk/duplex_control/state.py | [state](../src/xtalk/duplex_control/state.zh.md) |
| src/xtalk/duplex_control/timeline.py | [timeline](../src/xtalk/duplex_control/timeline.zh.md) |
| src/xtalk/serving/events.py | [events](../src/xtalk/serving/events.zh.md) |
| src/xtalk/serving/service.py | [service](../src/xtalk/serving/service.zh.md) |
| src/xtalk/serving/modules/llm_agent_context_manager.py | [llm_agent_context_manager](../src/xtalk/serving/modules/llm_agent_context_manager.zh.md) |
| src/xtalk/serving/modules/llm_agent_generation_manager.py | [llm_agent_generation_manager](../src/xtalk/serving/modules/llm_agent_generation_manager.zh.md) |
| src/xtalk/serving/modules/tts_manager.py | [tts_manager](../src/xtalk/serving/modules/tts_manager.zh.md) |
| src/xtalk/serving/modules/tts_response_coordinator.py | [tts_response_coordinator](../src/xtalk/serving/modules/tts_response_coordinator.zh.md) |
| src/xtalk/serving/modules/tts_playback_manager.py | [tts_playback_manager](../src/xtalk/serving/modules/tts_playback_manager.zh.md) |
| src/xtalk/serving/modules/turn_detector_manager.py | [turn_detector_manager](../src/xtalk/serving/modules/turn_detector_manager.zh.md) |
| tests/test_duplex_protocol.py | [test_duplex_protocol](../tests/test_duplex_protocol.zh.md) |
| tests/test_duplex_observability.py | [test_duplex_observability](../tests/test_duplex_observability.zh.md) |
| tests/test_turn_detector_manager.py | [test_turn_detector_manager](../tests/test_turn_detector_manager.zh.md) |

## 验证

~~~bash
conda run -n interclarify-dev python -m unittest tests.test_duplex_protocol tests.test_duplex_observability tests.test_turn_detector_manager tests.test_llm_agent_persistent_stream tests.test_response_identity tests.test_tool_call_playback_barrier tests.test_tts_streaming_playback_alignment -q
~~~

本地定向测试使用模拟生成与 PCM TTS 验证实际事件分发、并发响应隔离、预分配 ID、抢占、已播结算和关闭日志；静态编译与差异空白检查通过。真实模型、音频质量、同步磁盘写入开销和长会话需要远端 conda 环境单独验收。
