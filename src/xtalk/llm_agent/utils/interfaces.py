import asyncio
from abc import ABC, abstractmethod
from typing import Iterable, Union, TypedDict, AsyncIterator, Callable, Any
from langchain_core.messages import ToolCall
from langchain_core.tools import BaseTool
from ...pipelines.context import PipelineContext
from ..tools.utils import ToolCallResultPayload


class AgentInput(TypedDict):
    """Structured payload for agent generation input.

    Notes
    -----
    ``content`` stores the raw user text and ``context`` carries the current
    ``PipelineContext``.
    """

    content: str
    context: PipelineContext

AgentStreamItem = Union[str, ToolCall, ToolCallResultPayload]


class Agent(ABC):
    """Abstract interface for conversational agents used by Xtalk."""

    @abstractmethod
    def generate_stream(
        self, input: Union[str, AgentInput]
    ) -> Iterable[AgentStreamItem]:
        """Stream response chunks for the input.

        Parameters
        ----------
        input : str | AgentInput
            Raw user text or structured agent input.

        Yields
        ------
        str | ToolCall | ToolCallResultPayload
            Tool calls, tool-result payloads, and text chunks. Yield nothing
            when the turn should be skipped.
        """
        pass

    async def async_generate_stream(
        self, input: Union[str, AgentInput]
    ) -> AsyncIterator[AgentStreamItem]:
        """Asynchronously stream agent outputs.

        Parameters
        ----------
        input : str | AgentInput
            Raw user text or structured agent input.

        Yields
        ------
        str | ToolCall | ToolCallResultPayload
            Streamed outputs from ``generate_stream()``. No items are yielded
            when the turn is explicitly skipped.
        """

        loop = asyncio.get_running_loop()
        iterator = iter(self.generate_stream(input))
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
