# xtalk.llm_agent

## Agent

_定义于 `xtalk.llm_agent.interfaces`。_

```python
class Agent(ABC)
```

Xtalk 所使用的会话式 Agent 抽象接口。

## DummyAgent

_定义于 `xtalk.llm_agent.dummy`。_

```python
class DummyAgent(Agent)
```

用于测试的哑 LLM Agent。
该实现会忽略输入并返回预设响应。

## DefaultAgent

_定义于 `xtalk.llm_agent.default`。_

```python
class DefaultAgent(TemplateAgent)
```

构建在 `TemplateAgent` 之上的默认场景 Agent。

## TemplateAgent

_定义于 `xtalk.llm_agent.template`。_

```python
class TemplateAgent(Agent)
```

基于可复用 `ScenarioSpec` 模板构建的具体 `Agent` 实现。

## AgentRequest

_定义于 `xtalk.llm_agent.runtime`。_

```python
@dataclass
class AgentRequest
```

传入 Agent 运行时的单轮请求对象。

## AgentRuntime

_定义于 `xtalk.llm_agent.runtime`。_

```python
class AgentRuntime
```

面向单个会话、与具体场景无关的执行引擎。

## AgentSession

_定义于 `xtalk.llm_agent.runtime`。_

```python
@dataclass
class AgentSession
```

可变的会话级运行时状态。

## ContextAdapter

_定义于 `xtalk.llm_agent.runtime`。_

```python
class ContextAdapter(Protocol)
```

将 `PipelineContext` 转换为稳定 `TurnContext` 的适配协议。

## MutableToolProvider

_定义于 `xtalk.llm_agent.template`。_

```python
class MutableToolProvider(ToolProvider)
```

提供一组可在运行时扩展、且可安全克隆的工具列表。

## OutputPolicy

_定义于 `xtalk.llm_agent.runtime`。_

```python
class OutputPolicy(Protocol)
```

在输出下游消费者之前规范化模型文本的协议。

## PromptBuilder

_定义于 `xtalk.llm_agent.runtime`。_

```python
class PromptBuilder(Protocol)
```

构建场景特定提示词和用户消息的协议。

## ScenarioSpec

_定义于 `xtalk.llm_agent.runtime`。_

```python
@dataclass
class ScenarioSpec
```

注入到 `AgentRuntime` 中的场景定义。

## TextChunkEvent

_定义于 `xtalk.llm_agent.runtime`。_

```python
@dataclass
class TextChunkEvent
```

由运行时发出的纯文本片段事件。

## ToolCallEvent

_定义于 `xtalk.llm_agent.runtime`。_

```python
@dataclass
class ToolCallEvent
```

由模型请求执行的工具调用事件。

## ToolProvider

_定义于 `xtalk.llm_agent.runtime`。_

```python
class ToolProvider(Protocol)
```

返回当前场景和当前轮次可用工具的协议。

## ToolResultEvent

_定义于 `xtalk.llm_agent.runtime`。_

```python
@dataclass
class ToolResultEvent
```

由运行时发出的已完成工具结果事件。

## TurnContext

_定义于 `xtalk.llm_agent.runtime`。_

```python
@dataclass
class TurnContext
```

从 `PipelineContext` 派生出的、面向场景的结构化上下文。

## TurnHook

_定义于 `xtalk.llm_agent.runtime`。_

```python
class TurnHook(ABC)
```

用于在运行时执行前后注入场景特定行为的扩展点。
