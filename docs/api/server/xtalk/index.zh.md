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

- `MODEL_REGISTRY: dict[str, list[ImportSpec]]` = `SHARED_MODEL_REGISTRY`

### Methods

#### __init__

_定义于 `xtalk.api`。_

```python
def __init__(self, *, service_prototype: Service, max_sessions: int | None = None)
```

初始化 ``Xtalk`` 应用封装。

##### Parameters

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

##### Parameters

- `slot` (`str`)
  注册表槽位名称，例如 ``"llm_agent"`` 或 ``"tts"``。
- `spec` (`ImportSpec`)
  加载该槽位时要尝试的导入目标。支持模块路径、``"module:attribute"`` 引用以及 Python 文件路径。
- `prepend` (`bool, default=True`)
  是否在已有注册项之前优先尝试新的 spec。

##### Notes

常见的 ``spec`` 形式包括 ``"my_pkg.custom_tts"``、``"my_pkg.custom_tts:registry"``、``"/abs/path/custom_tts.py"`` 和 ``Path("./custom_tts.py")``。

##### Examples

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

##### Parameters

- `path_or_dict` (`str | dict`)
  JSON 文件路径或已加载的配置字典。

##### Returns

- `Xtalk`
  由 ``DefaultPipeline`` 和 ``DefaultService`` 支持的已配置应用封装。

##### Examples

```pycon
>>> xtalk = Xtalk.from_config("server_config.json")
```

#### create_pipeline_from_config

_定义于 `xtalk.api`。_

```python
def create_pipeline_from_config(cls, *, pipeline_cls: Type[Pipeline], config_path_or_dict: str | dict, additional_model_registry: dict[str, Any]) -> Pipeline
```

根据配置实例化自定义管道类。

##### Parameters

- `pipeline_cls` (`Type[Pipeline]`)
  要实例化的具体管道类型。
- `config_path_or_dict` (`str | dict`)
  JSON 文件路径或已加载的配置字典。
- `additional_model_registry` (`dict[str, Any]`)
  在创建管道前，额外合并到默认模型注册表上的槽位到实例映射。

##### Returns

- `Pipeline`
  根据提供的配置创建出的管道实例。

##### Examples

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

##### Parameters

- `limit` (`int`)
  同时允许存在的最大活跃会话数。

#### embed_text

_定义于 `xtalk.api`。_

```python
async def embed_text(self, session_id: str, text: str, user_id: str | None = None)
```

将文本加入会话级嵌入存储队列。

##### Parameters

- `session_id` (`str`)
  返回给前端的会话标识符。
- `text` (`str`)
  需要被嵌入并持久化用于检索的文本内容。

##### Raises

- `ValueError`
  当目标会话不存在时抛出。

#### add_agent_tools

_定义于 `xtalk.api`。_

```python
def add_agent_tools(self, tools_or_factories: list[BaseTool | Callable[[], BaseTool]])
```

在会话创建之前，将工具附加到原型 Agent 上。

##### Parameters

- `tools_or_factories` (`list[BaseTool | Callable[[], BaseTool]]`)
  工具实例，或能产生工具实例的零参数工厂函数。

##### Raises

- `RuntimeError`
  当至少一个服务会话已经被创建时抛出。

#### mount_routes

_定义于 `xtalk.api`。_

```python
def mount_routes(self, app: Any, *, login_path: str = '/api/auth/login', sessions_path: str = '/api/sessions', session_detail_path: str = '/api/sessions/{session_id}', upload_path: str = '/api/upload', ws_path: str = '/ws') -> None
```

挂载内置的登录、会话、上传和 WebSocket 路由。

#### connect

_定义于 `xtalk.api`。_

```python
async def connect(self, websocket: WebSocket, user_id: str | None = None)
```

接收一个 WebSocket 会话并将其交给服务管理器。

##### Parameters

- `websocket` (`WebSocket`)
  来自客户端的 FastAPI WebSocket 连接。
- `user_id` (`str | None, optional`)
  已认证的用户标识符。省略时，会退回到旧的基于连接作用域的会话行为。

##### Notes

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

#### context

_定义于 `xtalk.pipelines.interfaces`。_

```python
def context(self) -> 'PipelineContext'
```

返回由各个管理器共享的运行时上下文。

##### Returns

- `PipelineContext`
  首次访问时会以标准 Xtalk 运行时键初始化的可变上下文字典。

##### Notes

调用方通常会直接读取返回的字典。若要替换整个上下文，应通过 setter 完成。

## DefaultPipeline

_定义于 `xtalk.pipelines.default`。_

```python
@dataclass(init=False)
class DefaultPipeline(Pipeline)
```

保存会话使用的标准 Xtalk 模型集合。

## Service

_定义于 `xtalk.serving.service`。_

```python
class Service
```

编排会话作用域内的管道和管理器栈。

## DefaultService

_定义于 `xtalk.serving.service`。_

```python
class DefaultService(Service)
```

带有标准 Xtalk 管理器栈的便捷 ``Service``。

## BaseEvent

_定义于 `xtalk.serving.events`。_

```python
@dataclass
class BaseEvent
```

所有 Xtalk 事件的基础 dataclass。

## create_event_class

_定义于 `xtalk.serving.events`。_

```python
def create_event_class(*, name: str, fields: dict[str, Any] | None = None, type_name: str | None = None) -> Type[BaseEvent]
```

动态创建 ``BaseEvent`` 子类。

## Manager

_定义于 `xtalk.serving.interfaces`。_

```python
class Manager(EventListenerMixin, ShutdownMixin)
```

Xtalk 管理器的基类。

## EventBus

_定义于 `xtalk.serving.event_bus`。_

```python
class EventBus
```

发布和订阅会话事件，并支持异步分发。
