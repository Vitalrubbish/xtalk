您可以使用 `scripts/offline_client.py` 输入音频来测试 X-Talk。

## 从文本创建测试用例

如果您还没有准备好音频文件，可以使用 `scripts/create_test_case.py` 通过 DashScope TTS API 从转录文件生成音频。

首先，安装依赖并设置您的 API 密钥：

```bash
pip install requests
export DASHSCOPE_API_KEY=your_api_key
```

创建一个转录文件，每行格式为 `<时间戳>:<文本>`：

```plaintext
# transcription.txt
0:Hello, how are you today?
ai_end:I have another question for you.
ai_end+2.5:This will be sent 2.5 seconds after AI finishes.
```

其中 `<时间戳>` 可以是：

- 浮点数：从开始算起的绝对秒数（例如 `0`、`5.0`、`10.5`）
- `ai_start`：上一条用户音频触发的下一轮 AI 音频开始播放时
- `ai_end`：上一条用户音频触发的下一轮 AI 响应播放完成时
- `user_start`：上一条用户音频开始发送时
- `user_end`：上一条用户音频发送结束时
- `<标签>+<偏移量>`：该对应事件发生后的秒数（例如 `ai_end+2.5`）

相对时间按文件顺序解析。每一行都会等待与紧前一条已调度用户音频对应的首个匹配锚点事件。

然后运行脚本生成音频文件：

```bash
# 语音：Cherry（默认），语言：自动（默认）
python scripts/create_test_case.py --input transcription.txt --output /path/to/audio_dir

# 可选：指定语音和语言
python scripts/create_test_case.py --input transcription.txt --output /path/to/audio_dir --voice Cherry --language Chinese
```

这将创建：

- 音频文件：`audio_000.wav`、`audio_001.wav` 等
- `timestamp.txt` 文件，格式符合 `offline_client.py` 的要求

## 使用离线客户端运行测试

首先启动一个 X-Talk 服务器，记住端口号，例如 7634；在服务器配置文件中，添加以下代码片段以启用录音：
```json
"service_config": {
    "recording": true
}
```

然后为离线客户端安装依赖，并准备一个包含音频文件和 `timestamp.txt` 文件的音频目录用于测试：

```bash
pip install websockets soundfile numpy soxr
```
```plaintext
/path/to/audio_dir/
├── audio1.wav
├── audio2.wav
└── timestamp.txt

timestamp.txt 内容：
0:audio1.wav
ai_end:audio2.wav
ai_end+2.5:audio3.wav
```

然后使用服务器的 WebSocket URL 和输入音频目录运行离线客户端：

```bash
    python scripts/offline_client.py --ws ws://127.0.0.1:8000/ws --with-vad --input /path/to/audio_dir --output /path/to/recording.wav
```

您将在 `/path/to/recording.wav` 中看到结果。更多详情请参阅 `scripts/offline_client.py`。
