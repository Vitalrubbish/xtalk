# xtalk.model_types

## Embeddings

_定义于 `langchain_core.embeddings`。_

```python
from langchain_core.embeddings import Embeddings
```

该模块重新导出的外部依赖。

## BaseChatModel

_定义于 `langchain_core.language_models.chat_models`。_

```python
from langchain_core.language_models.chat_models import BaseChatModel
```

该模块重新导出的外部依赖。

## Agent

_定义于 `xtalk.llm_agent.interfaces`。_

```python
class Agent(ABC)
```

Xtalk 使用的会话式 Agent 抽象接口。

### Methods

- `generate`
  为输入生成完整响应。
- `generate_stream`
  为输入流式输出响应片段。
- `async_generate`
  异步生成完整响应。
- `async_generate_stream`
  异步流式输出 Agent 结果。
- `clone`
  为新会话克隆 Agent。
- `get_llm`
  返回 Agent 暴露的底层聊天模型。
- `get_chat_history`
  返回可用的序列化对话历史。
- `add_tools`
  向 Agent 附加工具。

## Rewriter

_定义于 `xtalk.rewriter.interfaces`。_

```python
class Rewriter(ABC)
```

文本重写辅助组件的抽象接口。

### Methods

- `rewrite`
  重写输入文本。
- `async_rewrite`
  异步重写输入文本。

## ASR

_定义于 `xtalk.speech.interfaces`。_

```python
class ASR(ABC)
```

自动语音识别的抽象接口。

### Methods

- `recognize`
  识别完整音频缓冲区。
- `recognize_stream`
  以流式模式增量识别音频。
- `stream_chunk_bytes_hint`
  返回建议的流式分块大小。
- `reset`
  重置内部识别状态。
- `clone`
  为新会话克隆 ASR 实例。
- `async_recognize`
  异步识别完整音频缓冲区。
- `async_recognize_stream`
  异步识别增量音频输入。

## TTS

_定义于 `xtalk.speech.interfaces`。_

```python
class TTS(ABC)
```

文本转语音引擎的抽象基类。

### Methods

- `synthesize`
  为完整文本输入合成音频。
- `synthesize_stream`
  为文本输入流式输出音频块。
- `async_synthesize`
  异步合成文本音频。
- `async_synthesize_stream`
  异步流式输出合成音频块。
- `clone`
  为新会话克隆 TTS 引擎。
- `set_voice`
  更新当前使用的音色。
- `set_emotion`
  更新当前合成情绪。

## Captioner

_定义于 `xtalk.speech.interfaces`。_

```python
class Captioner(ABC)
```

音频描述模型的抽象基类。

### Methods

- `caption`
  为音频生成描述文本。
- `caption_stream`
  为音频流式输出描述文本。
- `async_caption`
  异步生成音频描述。
- `async_caption_stream`
  异步流式输出描述文本。

## PuntRestorer

_定义于 `xtalk.speech.interfaces`。_

```python
class PuntRestorer(ABC)
```

标点恢复模型的抽象基类。

### Methods

- `restore`
  为文本恢复标点。
- `async_restore`
  异步恢复文本标点。

## VAD

_定义于 `xtalk.speech.interfaces`。_

```python
class VAD(ABC)
```

语音活动检测引擎的抽象基类。

### Methods

- `is_speech`
  判断音频帧是否包含语音。
- `async_is_speech`
  异步判断音频帧是否包含语音。

## SpeechEnhancer

_定义于 `xtalk.speech.interfaces`。_

```python
class SpeechEnhancer(ABC)
```

语音增强引擎的抽象基类。

### Notes

输入和输出都使用 16 kHz 的 PCM 16-bit 单声道音频字节。

### Methods

- `enhance`
  增强一帧音频。
- `flush`
  刷出内部缓冲音频。
- `async_enhance`
  异步增强音频。
- `async_flush`
  异步刷出缓冲音频。
- `reset`
  重置内部缓冲区和缓存。
- `clone`
  为新会话克隆语音增强器。

## SpeakerEncoder

_定义于 `xtalk.speech.interfaces`。_

```python
class SpeakerEncoder(ABC)
```

说话人嵌入模型的抽象基类。

### Methods

- `extract`
  生成说话人嵌入向量。
- `async_extract`
  异步提取说话人嵌入。
- `similarity`
  计算两个说话人嵌入之间的相似度。

## SpeechSpeedController

_定义于 `xtalk.speech.interfaces`。_

```python
class SpeechSpeedController(ABC)
```

TTS 语速控制器接口。

### Methods

- `process`
  对合成音频应用语速调整。
- `async_process`
  异步对音频应用语速调整。

## TurnDetector

_定义于 `xtalk.speech.interfaces`。_

```python
class TurnDetector(ABC)
```

轮次检测器的抽象接口。

### Methods

- `listening`
  读取或更新当前监听状态。
- `listening_lock`
  返回用于保护监听状态变更的锁。
- `detect`
  根据音频和/或文本检测当前对话轮次状态。
- `async_detect`
  异步检测当前对话轮次状态。
- `clone`
  为新会话克隆轮次检测器。
