from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
import asyncio
from typing import Any, AsyncIterator, Protocol, Sequence

from langchain.chat_models.base import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolCall,
    ToolMessage,
)
from langchain_core.tools import BaseTool

from ...log_utils import logger
from .interfaces import AgentContext

_SKIP_MODEL_KEY = "_agent_runtime_skip_model"
_REGISTER_TOOL_KEY = "_agent_runtime_register_tool"
_AGENT_CONTEXTS_KEY = "_agent_runtime_contexts"


@dataclass
class TurnContext:
    """Scenario-facing structured context derived from accepted agent updates.

    Parameters
    ----------
    speaker_id : str | None, optional
        Speaker identifier for the current user.
    caption : str | None, optional
        Caption-like non-verbal context for the turn.
    thought : str | None, optional
        Internal reasoning summary generated upstream.
    extras : dict[str, Any]
        Scenario-specific context fields that the runtime should not interpret.
    """

    speaker_id: str | None = None
    caption: str | None = None
    thought: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentSession:
    """Mutable per-session runtime state.

    Parameters
    ----------
    messages : list[BaseMessage]
        Conversation history, including system, user, assistant, and tool
        messages.
    metadata : dict[str, Any]
        Extensible per-session runtime metadata for scenario components.
    """

    messages: list[BaseMessage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ContextAdapter(Protocol):
    """Translate accepted agent context state into a stable ``TurnContext``."""

    def adapt(
        self,
        session: AgentSession,
        request: dict[str, Any],
    ) -> TurnContext:
        """Adapt session-scoped agent context for the current turn."""


def get_context_data(
    session: AgentSession,
    context_type: str,
) -> dict[str, Any]:
    """Return stored agent-context data for one logical context type.

    Parameters
    ----------
    session : AgentSession
        Mutable runtime session state.
    context_type : str
        Logical context stream name such as ``"thought"``.

    Returns
    -------
    dict[str, Any]
        Stored payload for the context type, or an empty dict.
    """

    raw_contexts = session.metadata.get(_AGENT_CONTEXTS_KEY)
    if not isinstance(raw_contexts, dict):
        return {}
    data = raw_contexts.get(context_type)
    if not isinstance(data, dict):
        return {}
    return dict(data)


class PromptBuilder(Protocol):
    """Build scenario-specific prompts and user messages."""

    def build_system_prompt(
        self,
        session: AgentSession,
        turn_context: TurnContext,
    ) -> str:
        """Build the system prompt for the current turn."""

    def build_user_message(
        self,
        request: dict[str, Any],
        turn_context: TurnContext,
    ) -> str:
        """Build the user-facing message content passed to the model."""


class ToolProvider(Protocol):
    """Return tools enabled for the current scenario and turn."""

    def get_tools(
        self,
        session: AgentSession,
        turn_context: TurnContext,
    ) -> Sequence[BaseTool]:
        """Return the tool set for the current turn."""


class OutputPolicy(Protocol):
    """Normalize model text before it is emitted to downstream consumers."""

    def filter_text(self, text: str) -> str:
        """Normalize one text fragment."""


class TurnHook(ABC):
    """Inject scenario-specific behavior around runtime execution."""

    async def before_model(
        self,
        request: dict[str, Any],
        session: AgentSession,
        turn_context: TurnContext,
    ) -> AsyncIterator["AgentEvent"]:
        """Emit events before model generation starts."""
        if False:
            yield

    async def after_tool(
        self,
        tool_name: str,
        tool_result: str,
        session: AgentSession,
        turn_context: TurnContext,
    ) -> AsyncIterator["AgentEvent"]:
        """Emit events after a tool finishes."""
        if False:
            yield


@dataclass
class ScenarioSpec:
    """Scenario definition injected into ``AgentRuntime``.

    Parameters
    ----------
    name : str
        Scenario identifier.
    context_adapter : ContextAdapter
        Adapter that turns accepted context state into stable turn context.
    prompt_builder : PromptBuilder
        Scenario-specific prompt and user-message builder.
    tool_provider : ToolProvider
        Tool selector for the current turn.
    output_policy : OutputPolicy
        Text normalization policy.
    hooks : Sequence[TurnHook]
        Optional scenario hooks around the runtime flow.
    """

    name: str
    context_adapter: ContextAdapter
    prompt_builder: PromptBuilder
    tool_provider: ToolProvider
    output_policy: OutputPolicy
    hooks: Sequence[TurnHook] = field(default_factory=list)


@dataclass
class TextChunkEvent:
    """Plain text chunk emitted by the runtime."""

    text: str


@dataclass
class ToolCallEvent:
    """Tool call requested by the model."""

    name: str
    args: dict[str, Any]
    call_id: str | None = None


@dataclass
class ToolResultEvent:
    """Completed tool result emitted by the runtime."""

    name: str
    args: dict[str, Any]
    content: str
    call_id: str | None = None


AgentEvent = TextChunkEvent | ToolCallEvent | ToolResultEvent


class AgentRuntime:
    """Scenario-agnostic execution engine for one conversational session.

    Parameters
    ----------
    model : BaseChatModel
        Bound chat model used for generation.
    scenario : ScenarioSpec
        Injected scenario definition.
    session : AgentSession | None, optional
        Existing mutable session state.
    """

    def __init__(
        self,
        model: BaseChatModel,
        scenario: ScenarioSpec,
        session: AgentSession | None = None,
    ) -> None:
        self.model = model
        self.scenario = scenario
        self.session = session or AgentSession()

    async def generate_stream(
        self,
        request: dict[str, Any],
    ) -> AsyncIterator[AgentEvent]:
        """Run one turn and stream typed runtime events.

        Parameters
        ----------
        request : dict[str, Any]
            Internal turn request.

        Yields
        ------
        AgentEvent
            Streamed text chunks, tool calls, and tool results.
        """

        turn_context = self.scenario.context_adapter.adapt(self.session, request)
        self._set_system_prompt(turn_context)
        self.session.metadata[_SKIP_MODEL_KEY] = False
        self.session.metadata[_REGISTER_TOOL_KEY] = self._register_dynamic_tool

        for hook in self.scenario.hooks:
            async for event in hook.before_model(request, self.session, turn_context):
                yield event
        if self.session.metadata.pop(_SKIP_MODEL_KEY, False):
            return

        tools = self.scenario.tool_provider.get_tools(self.session, turn_context)
        model_with_tools = self.model.bind_tools(tools) if tools else self.model
        tools_map = {tool.name: tool for tool in tools}

        user_content = self.scenario.prompt_builder.build_user_message(
            request,
            turn_context,
        )
        if turn_context.speaker_id:
            user_message = HumanMessage(
                content=user_content,
                name=turn_context.speaker_id,
            )
        else:
            user_message = HumanMessage(content=user_content)
        self.session.messages.append(user_message)

        while True:
            response_message = AIMessage(content="")
            self.session.messages.append(response_message)

            gathered = None
            async for chunk in model_with_tools.astream(self.session.messages):
                text = self.scenario.output_policy.filter_text(str(chunk.content or ""))
                if text:
                    response_message.content += text
                    yield TextChunkEvent(text=text)
                gathered = chunk if gathered is None else gathered + chunk

            tool_calls = (
                list(getattr(gathered, "tool_calls", []) or []) if gathered else []
            )
            if tool_calls:
                response_message.tool_calls = tool_calls
            if not tool_calls:
                return

            for tool_call in tool_calls:
                normalized_tool_call = self._normalize_tool_call(tool_call)
                yield ToolCallEvent(
                    name=normalized_tool_call["name"],
                    args=normalized_tool_call["args"],
                    call_id=normalized_tool_call["id"],
                )
                tool_result = await self._invoke_tool(
                    tools_map=tools_map,
                    tool_call=normalized_tool_call,
                )
                self.session.messages.append(tool_result)
                result_content = str(getattr(tool_result, "content", ""))
                for hook in self.scenario.hooks:
                    async for event in hook.after_tool(
                        normalized_tool_call["name"],
                        result_content,
                        self.session,
                        turn_context,
                    ):
                        yield event
                yield ToolResultEvent(
                    name=normalized_tool_call["name"],
                    args=normalized_tool_call["args"],
                    content=result_content,
                    call_id=normalized_tool_call["id"],
                )

    def accept(self, context: AgentContext) -> None:
        """Merge an incremental context update into the session state.

        Parameters
        ----------
        context : AgentContext
            Event-derived context update for the current session.
        """

        context_type = str(context.get("type", "") or "").strip()
        if not context_type:
            return None
        payload = context.get("data") or {}
        if not isinstance(payload, dict):
            return None

        raw_contexts = self.session.metadata.setdefault(_AGENT_CONTEXTS_KEY, {})
        if not isinstance(raw_contexts, dict):
            raw_contexts = {}
            self.session.metadata[_AGENT_CONTEXTS_KEY] = raw_contexts

        existing = raw_contexts.get(context_type)
        if not isinstance(existing, dict):
            existing = {}

        merged = dict(existing)
        merged.update(payload)
        raw_contexts[context_type] = merged
        return None

    def _register_dynamic_tool(self, tool: BaseTool) -> None:
        """Register a session-scoped tool for future turns."""
        dynamic_tools = self.session.metadata.setdefault("dynamic_tools", {})
        dynamic_tools[tool.name] = tool

    def _set_system_prompt(self, turn_context: TurnContext) -> None:
        """Ensure the first history message contains the current system prompt."""
        prompt = self.scenario.prompt_builder.build_system_prompt(
            self.session,
            turn_context,
        )
        if self.session.messages and isinstance(self.session.messages[0], SystemMessage):
            self.session.messages[0].content = prompt
            return
        self.session.messages.insert(0, SystemMessage(content=prompt))

    async def _invoke_tool(
        self,
        *,
        tools_map: dict[str, BaseTool],
        tool_call: ToolCall,
    ) -> ToolMessage:
        """Invoke one tool call and normalize the result as ``ToolMessage``."""
        name = tool_call["name"]
        tool = tools_map.get(name)
        if tool is None:
            return ToolMessage(
                content=f"Tool {name} not found",
                tool_call_id=tool_call["id"],
            )
        tool_input = tool_call.get("args", {})
        try:
            if hasattr(tool, "ainvoke"):
                result = await tool.ainvoke(tool_input)
            else:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, tool.invoke, tool_input)
            if isinstance(result, ToolMessage):
                return result
            return ToolMessage(
                content=str(result),
                tool_call_id=tool_call["id"],
            )
        except Exception as exc:
            logger.warning("Tool invocation failed for %s: %s", name, exc)
            return ToolMessage(
                content=f"Tool {name} invocation failed: {exc}",
                tool_call_id=tool_call["id"],
            )

    @staticmethod
    def _normalize_tool_call(tool_call: ToolCall | dict[str, Any]) -> ToolCall:
        """Convert LangChain tool-call payloads into a stable dict form."""
        if isinstance(tool_call, dict):
            name = str(tool_call.get("name") or tool_call.get("tool") or "")
            args = tool_call.get("args") or tool_call.get("arguments") or {}
            call_id = tool_call.get("id") or tool_call.get("tool_call_id")
            if isinstance(args, dict):
                return ToolCall(name=name, args=args, id=call_id)
        return tool_call
