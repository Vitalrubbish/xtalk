# llm_agent_generation_manager.py

## 功能、类与核心方法

每个异步 stream 保存独立响应状态和关联字段。首个文本使用预分配 response_id 或生成新 ID；首块、生成更新、TTS 请求、flush 和 finish 使用同一 request、turn、segment、prefix。完成时先复制元数据再清理状态，避免后续响应串线；停止仍保持原有会话范围和 persistent stream 行为。

## 状态与核心方法

_ResponseOutputState 持有每个 stream 的累计文本、response_id、首块和 TTS 标记及关联字段。_handle_generation_request 绑定来源；_consume_stream_item 发布首块、生成更新、TTS start/append；_finish_response_locked 复制完成状态后 reset 并发布 flush/finish；_wait_for_pre_tool_playback_locked 等待已播结算；shutdown 取消 stream 与工具任务。持久 stream 的关联字段描述其创建来源，后续 micro-turn 关联更新属于 A3。
