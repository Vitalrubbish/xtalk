# 服务配置项

`service_config` 是顶层配置中的一个可选对象，会传给 `DefaultService`，并在每个会话内共享给各个 manager 和 gateway。

示例：

```json
{
  "service_config": {
    "recording": true,
    "send_full_audio_to_client": false,
    "data_dir": "data"
  }
}
```

## 配置项列表

| 键名 | 类型 | 默认值 | 使用位置 | 作用 |
| --- | --- | --- | --- | --- |
| `data_dir` | `str` | `"data"` | `Service`、`EmbeddingsManager` | 会话级 embedding 数据的根目录。向量数据会持久化到 `<data_dir>/sessions/<session_id>/embeddings`，并在会话结束时删除对应会话目录。 |
| `recording` | `bool` | `false` | `RecordingManager` | 开启会话录音并输出为双声道 WAV 文件。左声道是原始用户音频，右声道是实际播放的 TTS 音频。默认输出路径为 `logs/session_audio/<timestamp>.wav`。 |
| `send_full_audio_to_client` | `bool` | `false` | `RecordingManager`、`OutputGateway`、前端 | 将拼装好的完整对话双声道 PCM 音频块通过 `full_audio_frame` 消息发给前端。数据格式为 48 kHz、16-bit、双声道 PCM，并以 base64 编码传输。 |
