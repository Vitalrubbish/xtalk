# xtalk.serving.module_types

## OutputGateway

_定义于 `xtalk.serving.modules.output_gateway`。_

```python
class OutputGateway(EventListenerMixin)
```

将后端事件转发到前端 WebSocket。

### Parameters

- `event_bus` (`EventBus`)
  用于订阅会话事件的事件总线。
- `session_id` (`str`)
  返回给前端的会话标识符。
- `websocket` (`WebSocket`)
  用于发送出站消息的实时 WebSocket 连接。
- `config` (`dict[str, Any] | None, optional`)
  与输出行为相关的服务配置。

### Methods

#### __init__

_定义于 `xtalk.serving.modules.output_gateway`。_

```python
def __init__(self, event_bus: EventBus, session_id: str, websocket: WebSocket, config: dict[str, Any] | None = None)
```

#### send_signal

_定义于 `xtalk.serving.modules.output_gateway`。_

```python
async def send_signal(self, message: dict) -> None
```

向前端发送 JSON 载荷。

##### Parameters

- `message` (`dict`)
  要通过 WebSocket 发送的可 JSON 序列化载荷。

#### send_session_attached

_定义于 `xtalk.serving.modules.output_gateway`。_

```python
async def send_session_attached(self) -> None
```

向前端发送已挂接的会话标识符。

## ASRManager

_定义于 `xtalk.serving.modules.asr_manager`。_

```python
class ASRManager(Manager)
```

## EmbeddingsManager

_定义于 `xtalk.serving.modules.embeddings_manager`。_

```python
class EmbeddingsManager(Manager)
```

## EnhancerManager

_定义于 `xtalk.serving.modules.enhancer_manager`。_

```python
class EnhancerManager(Manager)
```

后端语音增强管理器。

## LatencyManager

_定义于 `xtalk.serving.modules.latency_manager`。_

```python
class LatencyManager(EventListenerMixin)
```

监听 VAD、ASR、LLM、TTS 事件的会话级延迟跟踪器。

## LLMAgentManager

_定义于 `xtalk.serving.modules.llm_agent_manager`。_

```python
class LLMAgentManager(Manager)
```

驱动 LLM Agent 生成并协调 TTS 流式处理。

## SpeakerManager

_定义于 `xtalk.serving.modules.speaker_manager`。_

```python
class SpeakerManager(Manager)
```

会话作用域的说话人识别管理器。

## ThoughtManager

_定义于 `xtalk.serving.modules.thought_manager`。_

```python
class ThoughtManager(Manager)
```

周期性刷新对话 Thought 的管理器。

## TTSManager

_定义于 `xtalk.serving.modules.tts_manager`。_

```python
class TTSManager(Manager)
```

处理流式合成和控制的事件驱动 TTS 管理器。
类字段还包括 `TTS_CHUNK_MS = 100` 与 `MAX_OUTSTANDING_MS = 300`。

## TurnTakingManager

_定义于 `xtalk.serving.modules.turn_taking_manager`。_

```python
class TurnTakingManager(Manager)
```

## VADManager

_定义于 `xtalk.serving.modules.vad_manager`。_

```python
class VADManager(Manager)
```
