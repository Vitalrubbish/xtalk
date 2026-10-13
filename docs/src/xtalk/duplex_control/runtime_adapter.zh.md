# runtime_adapter.py

## 功能、类与核心方法

DuplexRuntimeAdapter 是唯一在线协议执行者，历史以 user 文本加模型服务返回的 assistant token id 保存，并持有回答 ID、生成文本和独立已播事实。_handle_micro_turn 串行推理、始终解码到 im_end 并观察协议；_append_user 发送增量并修订已发用户前缀；_request_history 构造由服务展平为官方 ChatML 的线上历史。_append_answer 复用回答和 TTS 流，并只对送 TTS 的文本去掉句点；思考时 _finish_answer flush。_apply_control 按到达顺序执行每个解码到的控制 token，并以动作前的 response ID 观察，重复或相邻 marker 均保持有效。finish talking 打开"正在播报"窗口；user is talking 与 user interruption 仅在该窗口内经 _reset_speaking 停止未播输出，对齐官方 tts_speaking_flag 门控。普通续写与用户附和保持同一流。_heard 只记录确认播放的单调前缀；shutdown 取消推理后停播。输入 final 不独立触发推理，重复 request 拒绝。

## 使用与边界

由 Service 的 duplex_enabled 布尔开关注册。原生模式保持既有配置；官方模型、长会话、音频质量与 FDB 需远端 conda 验收。

旧前缀版本拒绝为 stale_prefix；同版本空窗口仍可继续回答，生成期间新到的 ASR 在下一次调用处理，与官方串行机制一致。

识别到控制 token 后按到达顺序执行，其后的文本进入语音。"正在播报"窗口未打开时的 interruption 不改变播放。

协议观测保留动作前的 response ID，使停播/结束输入后的 token 仍关联到原回答。
