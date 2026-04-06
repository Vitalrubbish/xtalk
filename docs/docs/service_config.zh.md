# 服务配置项

`service_config` 是顶层配置中的一个可选对象，会传给 `DefaultService`，并在每个会话内共享给各个 manager 和 gateway。

示例：

```json
{
  "service_config": {
    "recording": true,
    "send_full_audio_to_client": false,
    "data_dir": "data",
    "vad_sample_rate": 16000,
    "vad_frame_samples": 512,
    "vad_min_speech_ms": 250,
    "vad_redemption_ms": 500,
    "similarity_threshold": 0.4,
    "min_audio_length_sec": 0.5,
    "embedding_update_alpha": 0.05,
    "debug_log_dir": "logs/speaker_debug"
  }
}
```

## 配置项列表

| 键名 | 类型 | 默认值 | 使用位置 | 作用 |
| --- | --- | --- | --- | --- |
| `data_dir` | `str` | `"data"` | `Service`、`EmbeddingsManager` | 会话级 embedding 数据的根目录。向量数据会持久化到 `<data_dir>/sessions/<session_id>/embeddings`，并在会话结束时删除对应会话目录。 |
| `recording` | `bool` | `false` | `RecordingManager` | 开启会话录音并输出为双声道 WAV 文件。左声道是原始用户音频，右声道是实际播放的 TTS 音频。默认输出路径为 `logs/session_audio/<timestamp>.wav`。 |
| `send_full_audio_to_client` | `bool` | `false` | `RecordingManager`、`OutputGateway`、前端 | 将拼装好的完整对话双声道 PCM 音频块通过 `full_audio_frame` 消息发给前端。数据格式为 48 kHz、16-bit、双声道 PCM，并以 base64 编码传输。 |
| `vad_sample_rate` | `int` | `16000` | `VADManager` | 后端 VAD 使用的采样率，用于计算帧时长。只有在 pipeline 中配置了后端 VAD 模型时才会生效。 |
| `vad_frame_samples` | `int` | `512` | `VADManager` | 后端 VAD 每帧的采样点数。它与 `vad_sample_rate` 一起决定单帧时长。 |
| `vad_min_speech_ms` | `int` | `250` | `VADManager` | 在发出 `VADSpeechStart` 之前，连续语音至少要累计到的时长。 |
| `vad_redemption_ms` | `int` | `500` | `VADManager` | 在发出 `VADSpeechEnd` 之前，需要累计到的静音时长。 |
| `similarity_threshold` | `float` | `0.4` | `SpeakerManager` | 当前轮次说话人与已有说话人画像做余弦相似度匹配时的阈值。低于该阈值会注册为新说话人。 |
| `min_audio_length_sec` | `float` | `0.5` | `SpeakerManager` | 进行说话人识别前，一个轮次内至少需要缓存的语音时长。更短的轮次会被标记为 `too_short`。 |
| `embedding_update_alpha` | `float` | `0.05` | `SpeakerManager` | 命中已有说话人后，用于更新其 embedding 的指数滑动平均权重。 |
| `debug_log_dir` | `str` | `"logs/speaker_debug"` | `SpeakerManager` | 预期的说话人调试产物输出目录。当前代码里调试落盘逻辑已被禁用，因此修改这个路径暂时不会产生可见效果，除非相关代码被重新启用。 |

## 说明

- 当前 `service_config` 的键是平铺的，还没有按模块做命名空间隔离。
- 未被现有 manager 使用的键会被忽略，除非您的自定义 manager 主动读取它们。
- 如果省略 `data_dir`，`Service` 会自动把它补成 `"data"`。
- `recording` 和 `send_full_audio_to_client` 相互独立，可以只开其中一个，也可以同时开启。

## 不属于 `service_config` 的项

`recording_path` 不属于静态 JSON 中的 `service_config`。
它是客户端通过 WebSocket `session_config` 消息按会话发送的运行时配置，
仅在启用录音时由 `RecordingManager` 消费。
