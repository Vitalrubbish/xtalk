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

Xtalk 所使用的会话式 Agent 抽象接口。

### Methods

#### generate

_定义于 `xtalk.llm_agent.interfaces`。_

```python
def generate(self, input: Union[str, AgentInput]) -> Union[str, tuple[str, List[ToolCall]]]
```

为输入生成完整响应。

##### Parameters

- `input` (`str | AgentInput`)
  原始用户文本，或同时包含文本和管道上下文的结构化载荷。

##### Returns

- `str | tuple[str, List[ToolCall]]`
  纯文本响应，或在需要暴露工具调用时返回 ``(text, tool_calls)`` 元组。

#### generate_stream

_定义于 `xtalk.llm_agent.interfaces`。_

```python
def generate_stream(self, input: Union[str, AgentInput]) -> Iterable[Union[str, ToolCall]]
```

为输入流式输出响应片段。

##### Parameters

- `input` (`str | AgentInput`)
  原始用户文本或结构化 Agent 输入。

##### Yields

- `str | ToolCall`
  工具调用以及文本片段。默认实现会委托给 ``generate()``，并以流式形式产出其结果。

#### async_generate

_定义于 `xtalk.llm_agent.interfaces`。_

```python
async def async_generate(self, input: Union[str, AgentInput]) -> Union[str, tuple[str, List[ToolCall]]]
```

异步生成完整响应。

##### Parameters

- `input` (`str | AgentInput`)
  原始用户文本或结构化 Agent 输入。

##### Returns

- `str | tuple[str, List[ToolCall]]`
  与 ``generate()`` 相同的结果约定。

#### async_generate_stream

_定义于 `xtalk.llm_agent.interfaces`。_

```python
async def async_generate_stream(self, input: Union[str, AgentInput]) -> AsyncIterator[Union[str, ToolCall]]
```

异步流式输出 Agent 结果。

##### Parameters

- `input` (`str | AgentInput`)
  原始用户文本或结构化 Agent 输入。

##### Yields

- `str | ToolCall`
  来自 ``generate_stream()`` 的流式输出。

#### clone

_定义于 `xtalk.llm_agent.interfaces`。_

```python
def clone(self) -> 'Agent'
```

为新会话克隆 Agent。

##### Returns

- `Agent`
  适用于会话的 Agent 实例。

#### get_llm

_定义于 `xtalk.llm_agent.interfaces`。_

```python
def get_llm(self) -> BaseChatModel | None
```

当 Agent 暴露聊天模型时，返回其底层聊天模型。

##### Returns

- `BaseChatModel | None`
  底层聊天模型；如果没有则为 ``None``。

#### get_chat_history

_定义于 `xtalk.llm_agent.interfaces`。_

```python
def get_chat_history(self) -> str | None
```

当可用时，返回序列化后的对话历史。

##### Returns

- `str | None`
  对话历史；如果没有则为 ``None``。

#### add_tools

_定义于 `xtalk.llm_agent.interfaces`。_

```python
def add_tools(self, tools: list[BaseTool | Callable[[], BaseTool]])
```

向 Agent 附加工具。

##### Parameters

- `tools` (`list[BaseTool | Callable[[], BaseTool]]`)
  工具实例，或返回工具实例的工厂函数。

## Rewriter

_定义于 `xtalk.rewriter.interfaces`。_

```python
class Rewriter(ABC)
```

文本重写辅助组件的抽象接口。

### Methods

#### rewrite

_定义于 `xtalk.rewriter.interfaces`。_

```python
def rewrite(self, input: str) -> str
```

重写输入文本。

##### Parameters

- `input` (`str`)
  待重写的源文本。

##### Returns

- `str`
  重写后的文本。

#### async_rewrite

_定义于 `xtalk.rewriter.interfaces`。_

```python
async def async_rewrite(self, input: str) -> str
```

异步重写输入文本。

##### Parameters

- `input` (`str`)
  待重写的源文本。

##### Returns

- `str`
  重写后的文本。

## ASR

_定义于 `xtalk.speech.interfaces`。_

```python
class ASR(ABC)
```

自动语音识别的抽象接口。

### Methods

#### recognize

_定义于 `xtalk.speech.interfaces`。_

```python
def recognize(self, audio: bytes) -> str
```

识别完整音频缓冲区。

##### Parameters

- `audio` (`bytes`)
  PCM 16-bit 单声道音频字节。

##### Returns

- `str`
  识别出的文本。

#### recognize_stream

_定义于 `xtalk.speech.interfaces`。_

```python
def recognize_stream(self, audio: bytes, *, is_final: bool = False) -> str
```

以流式模式增量识别音频。

##### Parameters

- `audio` (`bytes`)
  增量 PCM 16-bit 单声道音频字节。
- `is_final` (`bool, optional`)
  调用方是否因为用户停顿或轮次结束而强制进行最终解码。

##### Returns

- `str`
  当前识别结果。

#### stream_chunk_bytes_hint

_定义于 `xtalk.speech.interfaces`。_

```python
def stream_chunk_bytes_hint(self) -> int | None
```

返回建议的流式分块大小。

##### Returns

- `int | None`
  建议积累的字节数；如果没有偏好则为 ``None``。

#### reset

_定义于 `xtalk.speech.interfaces`。_

```python
def reset(self) -> None
```

重置内部识别状态。

#### clone

_定义于 `xtalk.speech.interfaces`。_

```python
def clone(self) -> 'ASR'
```

为新会话克隆 ASR 实例。

##### Returns

- `ASR`
  共享权重但具有独立运行时状态的克隆实例。

#### async_recognize

_定义于 `xtalk.speech.interfaces`。_

```python
async def async_recognize(self, audio: bytes) -> str
```

异步识别完整音频缓冲区。

##### Parameters

- `audio` (`bytes`)
  PCM 16-bit 单声道音频字节。

##### Returns

- `str`
  识别出的文本。

#### async_recognize_stream

_定义于 `xtalk.speech.interfaces`。_

```python
async def async_recognize_stream(self, audio: bytes, *, is_final: bool = False) -> str
```

异步识别增量音频输入。

##### Parameters

- `audio` (`bytes`)
  增量 PCM 16-bit 单声道音频字节。
- `is_final` (`bool, optional`)
  该分块是否应触发最终解码。

##### Returns

- `str`
  当前识别结果。

## TTS

_定义于 `xtalk.speech.interfaces`。_

```python
class TTS(ABC)
```

文本转语音引擎的抽象基类。

### Methods

#### synthesize

_定义于 `xtalk.speech.interfaces`。_

```python
def synthesize(self, text: str) -> bytes
```

为完整文本输入合成音频。

##### Parameters

- `text` (`str`)
  待合成文本。

##### Returns

- `bytes`
  48 kHz 的 PCM 16-bit 单声道音频字节。

#### synthesize_stream

_定义于 `xtalk.speech.interfaces`。_

```python
def synthesize_stream(self, text: str, **kwargs) -> Iterable[bytes]
```

为文本输入流式输出合成音频块。

##### Parameters

- `text` (`str`)
  待合成文本。
- `**kwargs`
  模型特定的流式选项。

##### Yields

- `bytes`
  48 kHz 的 PCM 16-bit 单声道音频字节。

## Captioner

_定义于 `xtalk.speech.interfaces`。_

```python
class Captioner(ABC)
```

音频描述模型的抽象基类。

## PuntRestorer

_定义于 `xtalk.speech.interfaces`。_

```python
class PuntRestorer(ABC)
```

标点恢复模型的抽象基类。

## VAD

_定义于 `xtalk.speech.interfaces`。_

```python
class VAD(ABC)
```

语音活动检测引擎的抽象基类。

## SpeechEnhancer

_定义于 `xtalk.speech.interfaces`。_

```python
class SpeechEnhancer(ABC)
```

语音增强引擎的抽象基类。

### Notes

输入与输出均使用 16 kHz 的 PCM 16-bit 单声道音频字节。

## SpeakerEncoder

_定义于 `xtalk.speech.interfaces`。_

```python
class SpeakerEncoder(ABC)
```

说话人嵌入模型的抽象基类。

## SpeechSpeedController

_定义于 `xtalk.speech.interfaces`。_

```python
class SpeechSpeedController(ABC)
```

TTS 语速控制器接口。

## TurnDetector

_定义于 `xtalk.speech.interfaces`。_

```python
class TurnDetector(ABC)
```

轮次检测器的抽象接口。
