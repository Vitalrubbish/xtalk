# output_gateway.py

`OutputGateway` 将后端转写、回答、TTS 和状态事件转换成前端消息，保留单一原生播放链路。

`send_session_attached()` 返回会话 ID 和 `acoustic_vad_enabled` 能力。浏览器与回放驱动在握手后据此关闭连续 ASR 会话的 VAD 检测和 speech start/end 发送。

`_send_vad_start_signal()` 和 `_send_vad_end_signal()` 在禁用声学 VAD 时不向客户端发送边界；启用时保持原行为，避免重复转发客户端产生的信号。TTS 音频及播放确认路径保持原协议。

能力从服务配置取得，默认启用。此输出层不负责推断用户说完，也不关闭 ASR 流。
