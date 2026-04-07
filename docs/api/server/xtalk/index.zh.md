# xtalk

## Xtalk

_定义于 `xtalk.api`。_

```python
class Xtalk
```

创建 Xtalk 管道、服务以及会话入口。

### Notes

``Xtalk`` 是示例应用使用的主要集成入口。它会根据配置构建管道，保存服务原型，并按需接收 WebSocket 会话。

### Class Fields

- `MODEL_REGISTRY: dict[str, list[ImportSpec]]` = `{'asr': ['xtalk.speech.asr'], 'llm_agent': ['xtalk.llm_agent'], 'tts': ['xtalk.speech.tts'], 'embeddings': ['xtalk.embeddings'], 'speaker_encoder': ['xtalk.speech.speaker_encoder'], 'captioner': ['xtalk.speech.captioner'], 'caption_rewriter': ['xtalk.rewriter'], 'thought_rewriter': ['xtalk.rewriter'], 'vad': ['xtalk.speech.vad'], 'speech_enhancer': ['xtalk.speech.speech_enhancer'], 'speech_speed_controller': ['xtalk.speech.speech_speed_controller'], 'turn_detector': ['xtalk.speech.turn_detector']}`

### Methods

#### __init__

_定义于 `xtalk.api`。_

```python
def __init__(self, *, service_prototype: Service, max_sessions: int | None = None)
```

初始化 ``Xtalk`` 应用封装。

### Parameters

- `service_prototype` (`Service`)
  用于克隆每个会话服务实例的服务原型。
- `max_sessions` (`int | None, optional`)
  最大并发会话数。如果省略，则不启用会话数量限制。

#### register_model_search_spec

_定义于 `xtalk.api`。_

```python
def register_model_search_spec(cls, *, slot: str, spec: ImportSpec, prepend: bool = True) -> None
```

为某个槽位注册额外的模型查找位置。

### Parameters

- `slot` (`str`)
  注册表槽位名称，例如 ``"llm_agent"`` 或 ``"tts"``。
- `spec` (`ImportSpec`)
  加载该槽位时要尝试的导入目标。支持模块路径、``"module:attribute"`` 引用以及 Python 文件路径。
- `prepend` (`bool, default=True`)
  是否在已有注册项之前优先尝试新的 `spec`。

### Notes

常见的 ``spec`` 形式包括 ``"my_pkg.custom_tts"``、``"my_pkg.custom_tts:registry"``、``"/abs/path/custom_tts.py"`` 和 ``Path("./custom_tts.py")``。

### Examples

```pycon
>>> Xtalk.register_model_search_spec(
...     slot="llm_agent",
...     spec="./echo_agent.py",
... )
```

#### from_config

_定义于 `xtalk.api`。_

```python
def from_config(cls, path_or_dict: str | dict) -> 'Xtalk'
```

根据配置数据构建 ``Xtalk`` 实例。

### Parameters

- `path_or_dict` (`str | dict`)
  JSON 文件路径或已加载的配置字典。

### Returns

- `Xtalk`
  由 ``DefaultPipeline`` 和 ``DefaultService`` 支持的已配置应用封装。

### Examples

```pycon
>>> xtalk = Xtalk.from_config("server_config.json")
```

#### create_pipeline_from_config

_定义于 `xtalk.api`。_

```python
def create_pipeline_from_config(cls, *, pipeline_cls: Type[Pipeline], config_path_or_dict: str | dict, additional_model_registry: dict[str, Any]) -> Pipeline
```

根据配置实例化自定义管道类。

### Parameters

- `pipeline_cls` (`Type[Pipeline]`)
  要实例化的具体管道类型。
- `config_path_or_dict` (`str | dict`)
  JSON 文件路径或已加载的配置字典。
- `additional_model_registry` (`dict[str, Any]`)
  在创建管道前，额外合并到默认模型注册表上的槽位到实例映射。

### Returns

- `Pipeline`
  根据提供的配置创建出的管道实例。

### Examples

```pycon
>>> pipeline = Xtalk.create_pipeline_from_config(
...     pipeline_cls=DefaultPipeline,
...     config_path_or_dict="server_config.json",
...     additional_model_registry={},
... )
```

#### set_session_limit

_定义于 `xtalk.api`。_

```python
def set_session_limit(self, limit: int)
```

设置或替换并发会话限制。

### Parameters

- `limit` (`int`)
  同时允许存在的最大活跃会话数。

#### embed_text

_定义于 `xtalk.api`。_

```python
async def embed_text(self, session_id: str, text: str)
```

将文本加入会话级嵌入存储队列。

### Parameters

- `session_id` (`str`)
  返回给前端的会话标识符。
- `text` (`str`)
  需要被嵌入并持久化用于检索的文本内容。

### Raises

- `ValueError`
  当目标会话不存在时抛出。

#### add_agent_tools

_定义于 `xtalk.api`。_

```python
def add_agent_tools(self, tools_or_factories: list[BaseTool | Callable[[], BaseTool]])
```

在会话创建之前，将工具附加到原型 Agent 上。

### Parameters

- `tools_or_factories` (`list[BaseTool | Callable[[], BaseTool]]`)
  工具实例，或能产生工具实例的零参数工厂函数。

### Raises

- `RuntimeError`
  当至少一个服务会话已经被创建时抛出。

#### connect

_定义于 `xtalk.api`。_

```python
async def connect(self, websocket: WebSocket)
```

接收一个 WebSocket 会话并将其交给服务管理器。

### Parameters

- `websocket` (`WebSocket`)
  来自客户端的 FastAPI WebSocket 连接。

### Notes

如果配置了会话数量限制，该连接会先经过会话限制器队列。

## Pipeline

_定义于 `xtalk.pipelines.interfaces`。_

```python
class Pipeline(ABC)
```

定义 Xtalk 服务所需的模型访问器。

### Notes

具体管道会暴露管理器所消费的模型和辅助对象。示例应用通常会继承 ``DefaultPipeline`` 来添加额外组件，同时保留这一接口。

### Methods

- `context`
  返回由各个管理器共享的运行时上下文。
- `clone`
  为新会话克隆管道。
- `get_asr_model`
  返回已配置的 ASR 模型。
- `get_tts_model`
  返回已配置的 TTS 模型。
- `get_agent`
  返回已配置的 Agent。
- `get_captioner_model`
  返回已配置的 Captioner。
- `get_punt_restorer_model`
  返回已配置的标点恢复模型。
- `get_caption_rewriter_model`
  返回 Caption 相关管理器使用的重写器。
- `get_thought_rewriter_model`
  返回 ``ThoughtManager`` 使用的重写器。
- `get_vad_model`
  返回已配置的语音活动检测器。
- `get_enhancer_model`
  返回已配置的语音增强器。
- `get_speaker_encoder`
  返回已配置的说话人编码器。
- `get_speed_controller`
  返回可选的 TTS 语速控制器。
- `get_embeddings_model`
  返回检索功能使用的嵌入模型。
- `get_turn_detector_model`
  返回已配置的轮次检测器。

## DefaultPipeline

_定义于 `xtalk.pipelines.default`。_

```python
@dataclass(init=False)
class DefaultPipeline(Pipeline)
```

保存会话使用的标准 Xtalk 模型集合。

### Parameters

- `asr` (`ASR`)
  语音识别模型。
- `llm_agent` (`Agent`)
  用于生成文本回复和工具调用的 Agent。
- `tts` (`TTS`)
  文本转语音模型。
- `default_response` (`str, optional`)
  没有更好回复时返回的兜底文本。
- `use_streaming_tts` (`bool, optional`)
  管理器在支持时是否优先使用流式 TTS。
- `captioner` (`Captioner | None, optional`)
  可选的音频描述模型。
- `punt_restorer_model` (`PuntRestorer | None, optional`)
  可选的标点恢复模型。
- `caption_rewriter` (`Rewriter | BaseChatModel | None, optional`)
  可选的 Caption 重写器，或会被包装成重写器的聊天模型。
- `thought_rewriter` (`Rewriter | BaseChatModel | None, optional`)
  可选的 Thought 重写器，或会被包装成重写器的聊天模型。
- `vad` (`VAD | None, optional`)
  可选的语音活动检测器。
- `speech_enhancer` (`SpeechEnhancer | None, optional`)
  可选的语音增强模型。
- `speaker_encoder` (`SpeakerEncoder | None, optional`)
  可选的说话人嵌入模型。
- `speech_speed_controller` (`SpeechSpeedController | None, optional`)
  用于合成音频后处理的可选语速控制器。
- `embeddings` (`Embeddings | None, optional`)
  用于检索功能的可选嵌入后端。
- `turn_detector` (`TurnDetector | None, optional`)
  协调打断与生成的可选轮次检测器。

### Notes

dataclass 字段元数据控制着每个会话实例如何被克隆。子类只要暴露 ``init_key`` 元数据字段，就可以继续添加新字段。

### Methods

- `clone`
  根据字段元数据克隆管道。
- `set_tts_model`
  在运行时切换当前激活的 TTS 模型。
- `set_llm_model`
  用 ``ChatOpenAI`` 实例替换当前 Agent 的 LLM。

## Service

_定义于 `xtalk.serving.service`。_

```python
class Service
```

编排会话作用域内的管道和管理器栈。

### Parameters

- `pipeline` (`Pipeline`)
  将在该会话中被克隆的管道原型。
- `service_config` (`dict[str, Any] | None, optional`)
  在管理器和网关之间共享的会话配置。
- `manager_classes` (`list[Type[Manager]] | None, optional`)
  用于实时会话的管理器类列表。
- `_websocket` (`WebSocket | None, optional`)
  用于实时会话的内部 WebSocket 句柄。``None`` 表示该实例仅作为原型。
- `_event_overrides` (`dict[Type[EventListenerMixin], EventOverrides] | None, optional`)
  复制到克隆会话中的内部事件订阅重写配置。

### Methods

- `unsubscribe_event`
  禁用某个监听器类的自动事件订阅。
- `subscribe_event`
  注册额外的事件订阅重写。
- `register_manager`
  向服务注册一个管理器类。
- `unregister_manager`
  从服务中移除一个管理器类。
- `handle_message_loop`
  运行实时会话的完整 WebSocket 消息循环。
- `stop`
  停止服务并关闭所有管理器。
- `clone`
  为新的 WebSocket 会话克隆服务原型。

## DefaultService

_定义于 `xtalk.serving.service`。_

```python
class DefaultService(Service)
```

带有标准 Xtalk 管理器栈的便捷 ``Service``。

### Notes

示例应用通常会直接实例化 ``DefaultService``，然后通过注册或重写 Manager 来实现自定义行为。

## BaseEvent

_定义于 `xtalk.serving.events`。_

```python
@dataclass
class BaseEvent
```

所有 Xtalk 事件的基础 dataclass。

### Parameters

- `session_id` (`str`)
  与该事件关联的会话标识符。

### Attributes

- `timestamp` (`float`)
  记录事件实例创建时的 Unix 时间戳。
- `session_id` (`str`)
  与该事件关联的会话标识符。
- `TYPE` (`str`)
  事件总线使用的稳定事件类型字符串。

## create_event_class

_定义于 `xtalk.serving.events`。_

```python
def create_event_class(*, name: str, fields: dict[str, Any] | None = None, type_name: str | None = None) -> Type[BaseEvent]
```

动态创建 ``BaseEvent`` 子类。

### Parameters

- `name` (`str`)
  生成事件类型的 dataclass 名称。
- `fields` (`dict[str, Any] | None, optional`)
  字段名到默认值的映射。值的类型会从默认值推断。
- `type_name` (`str | None, optional`)
  事件总线类型字符串。省略时默认使用 ``name.lower()``。

### Returns

- `Type[BaseEvent]`
  继承自 ``BaseEvent`` 的生成 dataclass 类型。

### Examples

```pycon
>>> CustomEvent = create_event_class(
...     name="CustomEvent",
...     fields={"text": "", "turn_id": 0},
... )
```

## Manager

_定义于 `xtalk.serving.interfaces`。_

```python
class Manager(EventListenerMixin, ShutdownMixin)
```

Xtalk 管理器的基类。

### Notes

子类通常接收 ``event_bus``、``session_id``、``pipeline`` 和 ``config`` 参数，然后通过 ``@Manager.event_handler`` 注册处理器。

### Methods

#### event_handler

_定义于 `xtalk.serving.interfaces`。_

```python
def event_handler(event_type: Type[BaseEvent], *, priority: int = 0, enabled_if: Callable[['EventListenerMixin'], bool] | None = None)
```

声明一个管理器事件处理器。

### Parameters

- `event_type` (`Type[BaseEvent]`)
  被装饰方法处理的事件类。
- `priority` (`int, optional`)
  处理器执行优先级。值越大越先执行。
- `enabled_if` (`Callable[[EventListenerMixin], bool] | None, optional`)
  在注册处理器前，对管理器实例求值的谓词。

### Returns

- `Callable`
  用于将方法标记为自动订阅处理器的装饰器。

## EventBus

_定义于 `xtalk.serving.event_bus`。_

```python
class EventBus
```

发布和订阅会话事件，并支持异步分发。

### Parameters

- `enable_history` (`bool, optional`)
  是否在内存中保存已发布事件以供后续查看。
- `max_history` (`int, optional`)
  启用历史记录时最多保留的事件数量。

### Methods

- `subscribe`
  为某种事件类型订阅处理器。
- `unsubscribe`
  从某种事件类型取消订阅处理器。
- `publish`
  向所有匹配处理器发布一个事件。
- `get_history`
  按可选过滤条件获取事件历史。
- `get_stats`
  返回当前事件总线统计信息。
- `clear_history`
  清空事件历史。
- `reset_error_tracking`
  重置错误事件跟踪状态。
- `shutdown`
  关闭事件总线并释放资源。
