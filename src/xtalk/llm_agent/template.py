"""Reusable template-backed agent implementations for scenario-driven flows."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import Any, AsyncIterator, Callable, Coroutine, Iterable, Optional, Protocol, TypeVar, Union

from langchain.chat_models.base import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolCall
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from ..log_utils import logger
from .interfaces import Agent, AgentInput
from .runtime import (
    AgentRequest,
    AgentRuntime,
    TextChunkEvent,
    ToolCallEvent,
    ToolProvider,
    ToolResultEvent,
    TurnContext,
    ScenarioSpec,
)
from .tools.utils import build_tool_call_result_payload

T = TypeVar("T")


def _format_chat_history(
    messages: list[BaseMessage],
    *,
    with_system: bool = False,
) -> str | None:
    """Render plain-text chat history from LangChain messages.

    Parameters
    ----------
    messages : list[BaseMessage]
        Session message history.
    with_system : bool, optional
        Whether to include system messages in the rendered output.

    Returns
    -------
    str | None
        Serialized conversation history, or ``None`` when unavailable.
    """

    if not messages:
        return None
    lines: list[str] = []
    for message in messages:
        role = "System"
        if isinstance(message, HumanMessage):
            role = "User"
        elif isinstance(message, AIMessage):
            role = "Assistant"
        if role == "System" and not with_system:
            continue
        content = message.content
        lines.append(f"{role}: {content if isinstance(content, str) else str(content)}")
    return "\n".join(lines)


class SupportsMutableToolProvider(Protocol):
    """Protocol for tool providers that can be extended and cloned safely."""

    def add_tools(self, tools: list[BaseTool | Callable[[], BaseTool]]) -> None:
        """Append tool instances or factories."""

    def get_tool_specs(self) -> list[Callable[[], BaseTool]]:
        """Return clone-safe tool factories."""


class MutableToolProvider(ToolProvider):
    """Provide a clone-safe list of tools that can be extended at runtime.

    Parameters
    ----------
    tools : list[BaseTool | Callable[[], BaseTool]] | None, optional
        Initial tool instances or factories.
    """

    def __init__(
        self,
        tools: Optional[list[BaseTool | Callable[[], BaseTool]]] = None,
    ) -> None:
        self._tool_factories = self.normalize_tool_specs(tools or [])

    def add_tools(
        self,
        tools: list[BaseTool | Callable[[], BaseTool]],
    ) -> None:
        """Append tools or tool factories.

        Parameters
        ----------
        tools : list[BaseTool | Callable[[], BaseTool]]
            Tool instances or factories to append.
        """

        self._tool_factories.extend(self.normalize_tool_specs(tools))

    def get_tool_specs(self) -> list[Callable[[], BaseTool]]:
        """Return clone-safe tool factories.

        Returns
        -------
        list[Callable[[], BaseTool]]
            Normalized factories used by this provider.
        """

        return list(self._tool_factories)

    def get_tools(self, session, turn_context) -> list[BaseTool]:
        """Return session-scoped tool instances for the current turn.

        Parameters
        ----------
        session : Any
            Runtime session state used to cache tool instances.
        turn_context : Any
            Structured turn context. Unused by the base implementation.

        Returns
        -------
        list[BaseTool]
            Tool instances reused within the current session.
        """

        del turn_context
        cache_key = f"_mutable_tool_provider_cache_{id(self)}"
        cached_tools = session.metadata.get(cache_key)
        if isinstance(cached_tools, list) and all(
            isinstance(tool, BaseTool) for tool in cached_tools
        ):
            return cached_tools

        tools: list[BaseTool] = []
        for factory in self._tool_factories:
            try:
                tool = factory()
            except Exception as exc:
                logger.warning("Tool factory %r failed: %s", factory, exc)
                continue
            if isinstance(tool, BaseTool):
                tools.append(tool)
            else:
                logger.warning(
                    "Tool factory %r returned non-BaseTool: %s",
                    factory,
                    type(tool),
                )
        session.metadata[cache_key] = tools
        return tools

    @staticmethod
    def normalize_tool_specs(
        tools: list[BaseTool | Callable[[], BaseTool]],
    ) -> list[Callable[[], BaseTool]]:
        """Normalize tools into zero-argument factories.

        Parameters
        ----------
        tools : list[BaseTool | Callable[[], BaseTool]]
            Tool instances or factories.

        Returns
        -------
        list[Callable[[], BaseTool]]
            Factory list.
        """

        factories: list[Callable[[], BaseTool]] = []
        for tool in tools:
            if isinstance(tool, BaseTool):
                factories.append(lambda tool=tool: tool)
            elif callable(tool):
                factories.append(tool)
            else:
                logger.warning("Unsupported tool spec: %r", tool)
        return factories


class TemplateAgent(Agent):
    """Concrete ``Agent`` built from a reusable ``ScenarioSpec`` template.

    Parameters
    ----------
    model : BaseChatModel | dict[str, Any]
        Chat model instance or ``ChatOpenAI`` configuration.
    scenario : ScenarioSpec
        Scenario definition used by the runtime.
    clone_kwargs : dict[str, Any] | None, optional
        Keyword arguments reused when ``clone()`` creates a fresh session agent.
        The ``model`` argument is supplied automatically and should not be
        included here.
    tool_provider : SupportsMutableToolProvider | None, optional
        Mutable tool provider used to implement ``add_tools()`` and preserve
        tool factories across ``clone()``.
    tool_specs_key : str | None, optional
        ``clone_kwargs`` key that should receive ``tool_provider`` factories
        during cloning. Set to ``None`` when tool specs should not be injected.
    """

    def __init__(
        self,
        model: BaseChatModel | dict[str, Any],
        *,
        scenario: ScenarioSpec,
        clone_kwargs: dict[str, Any] | None = None,
        tool_provider: SupportsMutableToolProvider | None = None,
        tool_specs_key: str | None = "tools",
    ) -> None:
        resolved_model = self.coerce_model(model)
        self._model = resolved_model
        self.runtime = AgentRuntime(model=resolved_model, scenario=scenario)
        self._clone_kwargs = dict(clone_kwargs or {})
        self._tool_provider = tool_provider
        self._tool_specs_key = tool_specs_key

    @staticmethod
    def coerce_model(model: BaseChatModel | dict[str, Any]) -> BaseChatModel:
        """Coerce model configuration into a concrete chat model.

        Parameters
        ----------
        model : BaseChatModel | dict[str, Any]
            Chat model instance or ``ChatOpenAI`` configuration dict.

        Returns
        -------
        BaseChatModel
            Concrete chat model instance.
        """

        if isinstance(model, dict):
            return ChatOpenAI(**model)
        return model

    @property
    def model(self) -> BaseChatModel:
        """Return the backing model."""

        return self._model

    @model.setter
    def model(self, model: BaseChatModel) -> None:
        """Update the backing model and runtime.

        Parameters
        ----------
        model : BaseChatModel
            New backing model.
        """

        self._model = model
        self.runtime.model = model

    @property
    def session_history(self) -> list[BaseMessage]:
        """Expose runtime session history for compatibility."""

        return self.runtime.session.messages

    @session_history.setter
    def session_history(self, messages: list[BaseMessage]) -> None:
        """Replace runtime session history for compatibility.

        Parameters
        ----------
        messages : list[BaseMessage]
            New session message list.
        """

        self.runtime.session.messages = messages

    @contextmanager
    def _temporary_event_loop(self) -> Iterable[asyncio.AbstractEventLoop]:
        """Create a temporary event loop and clean it up on exit."""

        loop = asyncio.new_event_loop()
        try:
            yield loop
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            try:
                loop.run_until_complete(loop.shutdown_default_executor())
            except Exception:
                pass
            loop.close()

    def _run_async_task(self, coro: Coroutine[Any, Any, T]) -> T:
        """Execute a coroutine in a temporary event loop.

        Parameters
        ----------
        coro : Coroutine[Any, Any, T]
            Coroutine to execute.

        Returns
        -------
        T
            Coroutine result.
        """

        with self._temporary_event_loop() as loop:
            return loop.run_until_complete(coro)

    def _sync_iter_from_async(self, async_iter: AsyncIterator[T]) -> Iterable[T]:
        """Convert an async iterator into a synchronous generator.

        Parameters
        ----------
        async_iter : AsyncIterator[T]
            Async iterator to bridge.

        Yields
        ------
        T
            Streamed items.
        """

        with self._temporary_event_loop() as loop:
            try:
                while True:
                    try:
                        item = loop.run_until_complete(async_iter.__anext__())
                    except StopAsyncIteration:
                        break
                    yield item
            finally:
                aclose = getattr(async_iter, "aclose", None)
                if callable(aclose):
                    try:
                        loop.run_until_complete(aclose())
                    except Exception:
                        pass

    @staticmethod
    def _build_request(input: Union[str, AgentInput]) -> AgentRequest:
        """Normalize legacy agent input into ``AgentRequest``.

        Parameters
        ----------
        input : str | AgentInput
            Legacy agent input.

        Returns
        -------
        AgentRequest
            Structured runtime request.
        """

        if isinstance(input, dict):
            context = input.get("context")
            return AgentRequest(
                content=str(input.get("content", "")),
                context=context if isinstance(context, dict) else None,
            )
        return AgentRequest(content=str(input))

    @staticmethod
    def _to_tool_call(event: ToolCallEvent) -> ToolCall:
        """Convert a typed tool-call event into the legacy payload.

        Parameters
        ----------
        event : ToolCallEvent
            Typed runtime event.

        Returns
        -------
        ToolCall
            Legacy tool-call payload.
        """

        return ToolCall(name=event.name, args=dict(event.args), id=event.call_id)

    def generate(
        self,
        input: Union[str, AgentInput],
    ) -> Union[str, tuple[str, list[ToolCall]]]:
        """Generate a complete response.

        Parameters
        ----------
        input : str | AgentInput
            Legacy agent input.

        Returns
        -------
        str | tuple[str, list[ToolCall]]
            Response text, plus tool calls when any occurred.
        """

        return self._run_async_task(self.async_generate(input))

    async def async_generate(
        self,
        input: Union[str, AgentInput],
    ) -> Union[str, tuple[str, list[ToolCall]]]:
        """Asynchronously generate a complete response.

        Parameters
        ----------
        input : str | AgentInput
            Legacy agent input.

        Returns
        -------
        str | tuple[str, list[ToolCall]]
            Response text, plus tool calls when any occurred.
        """

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        async for event in self.runtime.generate_stream(self._build_request(input)):
            if isinstance(event, TextChunkEvent):
                text_parts.append(event.text)
            elif isinstance(event, ToolCallEvent):
                tool_calls.append(self._to_tool_call(event))
        text = "".join(text_parts)
        if tool_calls:
            return text, tool_calls
        return text

    def generate_stream(
        self,
        input: Union[str, AgentInput],
    ) -> Iterable[Union[str, ToolCall, dict[str, Any]]]:
        """Synchronously stream legacy response chunks.

        Parameters
        ----------
        input : str | AgentInput
            Legacy agent input.

        Yields
        ------
        str | ToolCall | dict[str, Any]
            Text chunks, legacy tool-call payloads, and tool-result payloads.
        """

        yield from self._sync_iter_from_async(self.async_generate_stream(input))

    async def async_generate_stream(
        self,
        input: Union[str, AgentInput],
    ) -> AsyncIterator[Union[str, ToolCall, dict[str, Any]]]:
        """Asynchronously stream legacy response chunks.

        Parameters
        ----------
        input : str | AgentInput
            Legacy agent input.

        Yields
        ------
        str | ToolCall | dict[str, Any]
            Text chunks, legacy tool-call payloads, and tool-result payloads.
        """

        async for event in self.runtime.generate_stream(self._build_request(input)):
            if isinstance(event, TextChunkEvent):
                yield event.text
            elif isinstance(event, ToolCallEvent):
                yield self._to_tool_call(event)
            elif isinstance(event, ToolResultEvent):
                yield build_tool_call_result_payload(
                    name=event.name,
                    args=event.args,
                    content=event.content,
                )

    def restore_history(self, messages: list[dict[str, Any]]) -> None:
        """Restore persisted conversation history into the runtime session.

        Parameters
        ----------
        messages : list[dict[str, Any]]
            Persisted chat messages.
        """

        restored: list[BaseMessage] = [
            SystemMessage(
                content=self.runtime.scenario.prompt_builder.build_system_prompt(
                    self.runtime.session,
                    TurnContext(),
                )
            )
        ]
        for message in messages:
            role = message.get("role")
            content = str(message.get("content", ""))
            if role == "user":
                restored.append(HumanMessage(content=content))
            elif role == "assistant":
                restored.append(AIMessage(content=content))
        self.runtime.session.messages = restored

    def get_chat_history(self, with_system: bool = False) -> str | None:
        """Render plain-text chat history.

        Parameters
        ----------
        with_system : bool, optional
            Whether to include the system message.

        Returns
        -------
        str | None
            Serialized chat history.
        """

        try:
            return _format_chat_history(
                self.runtime.session.messages,
                with_system=with_system,
            )
        except Exception as exc:
            logger.warning("Failed to build chat history: %s", exc)
            return None

    def clone(self) -> "TemplateAgent":
        """Clone the agent with a fresh session.

        Returns
        -------
        TemplateAgent
            Session-safe cloned agent.
        """

        clone_kwargs = dict(self._clone_kwargs)
        if self._tool_provider is not None and self._tool_specs_key:
            clone_kwargs[self._tool_specs_key] = self._tool_provider.get_tool_specs()
        return type(self)(model=self.model, **clone_kwargs)

    def add_tools(self, tools: list[BaseTool | Callable[[], BaseTool]]) -> None:
        """Attach additional tools to the scenario.

        Parameters
        ----------
        tools : list[BaseTool | Callable[[], BaseTool]]
            Tool instances or factories.

        Raises
        ------
        RuntimeError
            Raised when the configured tool provider is not mutable.
        """

        if not tools:
            return
        if self._tool_provider is None:
            raise RuntimeError("This agent does not expose a mutable tool provider.")
        self._tool_provider.add_tools(tools)
