# TTS 接口与取消边界

`TTS` 定义完整文本 synthesize 和可选同步/异步音频流，标准输出为48kHz mono PCM16；clone提供会话隔离。`StreamingTextTTS` 接收实时文本，start开启响应，append_text追加，flush结束当前输入并请求尾部，stop用于结束并释放，audio_stream只交付PCM给既有管理器。

新增默认cancel调用旧提供者的stop，保持兼容；支持正常排空与强制取消分离的提供者可重写。KokoroSegmented重写cancel以先失效代际、再取消传输；TTSManager在reset/插话路径调用cancel，正常flush路径仍调用stop。接口不拥有播放器或跨层仲裁权。
