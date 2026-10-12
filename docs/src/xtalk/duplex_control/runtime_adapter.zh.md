# runtime_adapter.py

## 功能、类与核心方法

DuplexRuntimeAdapter 是唯一在线协议执行者，持有 raw micro-turn 历史、回答 ID、生成文本和独立已播事实。_handle_micro_turn 串行推理并观察协议；_append_user 发送增量并修订已发用户前缀；_prompt 使用官方 ChatML。_append_answer 复用回答和 TTS 流；思考时 _finish_answer flush。完整 interruption marker 会经 _stop_answer 停止未播输出、关闭当前模型流并立即结束当前 micro-turn，不等待 im_end；事件保留模型实际 token，只有 prompt 历史形式内部补入 ChatML 闭合符。普通续写与用户附和保持同一流。_heard 只记录确认播放的单调前缀；shutdown 取消推理后停播。输入 final 不独立触发推理，重复 request 拒绝。

## 使用与边界

由 Service 的 duplex_enabled 布尔开关注册。原生模式保持既有配置；官方模型、长会话、音频质量与 FDB 需远端 conda 验收。

旧前缀版本拒绝为 stale_prefix；同版本空窗口仍可继续回答，生成期间新到的 ASR 在下一次调用处理，与官方串行机制一致。

识别到 interruption marker 后立即停播并关闭模型流；它是唯一不要求 EOS 的终止控制。其他控制仍按正常规则验证 EOS。

协议观测保留动作前的 response ID，使停播/结束输入后的 token 仍关联到原回答。
