import asyncio
from abc import ABC, abstractmethod
from typing import Iterable, TypedDict, AsyncIterator, Callable, Any, Union
from langchain_core.messages import ToolCall
from langchain_core.tools import BaseTool
from ..tools.utils import ToolCallResultPayload


class AgentContext(TypedDict):
    """Incremental context update accepted by an agent.

    Notes
    -----
    ``type`` identifies the logical context stream, while ``data`` carries the
    event-derived payload for that stream.
    """

    type: str
    data: dict[str, Any]


AgentOutput = Union[str, ToolCall, ToolCallResultPayload]


class Agent(ABC):
    """Abstract interface for conversational agents used by Xtalk."""

    @abstractmethod
    def accept(self, context: AgentContext) -> Iterable[AgentOutput]:
        """Accept an incremental context update.

        Parameters
        ----------
        context : AgentContext
            Context payload forwarded from serving-layer events.

        Yields
        ------
        AgentStreamItem
            Zero or more streamed response items triggered by the context
            update.
        """
        pass

    async def async_accept(self, context: AgentContext) -> AsyncIterator[AgentOutput]:
        """Asynchronously accept an incremental context update.

        Parameters
        ----------
        context : AgentContext
            Context payload forwarded from serving-layer events.

        Yields
        ------
        AgentStreamItem
            Streamed response items triggered by the context update.
        """

        loop = asyncio.get_running_loop()
        iterator = iter(self.accept(context))
        sentinel = object()

        try:
            while True:

                def _next_item():
                    try:
                        return next(iterator)
                    except StopIteration:
                        return sentinel

                item = await loop.run_in_executor(None, _next_item)
                if item is sentinel:
                    break
                yield item
        finally:
            close = getattr(iterator, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    @abstractmethod
    def clone(self) -> "Agent":
        """Clone the agent for a new session.

        Returns
        -------
        Agent
            Session-safe agent instance.
        """
        pass

    @abstractmethod
    def restore_history(self, messages: list[dict[str, Any]]) -> None:
        """Restore persisted conversation messages into the agent state.

        Parameters
        ----------
        messages : list[dict[str, Any]]
            Persisted chat messages ordered by session history.
        """
        pass

    def get_chat_history(self, with_system: bool = False) -> str | None:
        """Return the serialized conversation history when available.

        Parameters
        ----------
        with_system : bool, optional
            Whether to include the system prompt message when supported by the
            concrete implementation.

        Returns
        -------
        str | None
            Conversation history or ``None``.
        """
        return None

    def add_tools(self, tools: list[BaseTool | Callable[[], BaseTool]]) -> None:
        """Attach tools to the agent.

        Parameters
        ----------
        tools : list[BaseTool | Callable[[], BaseTool]]
            Tool instances or factories that produce tool instances.
        """
        pass
