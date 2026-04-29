"""Lightweight dummy agent implementation for tests and sample wiring."""

from typing import Any, Iterable, Union

from .utils.interfaces import Agent, AgentInput, AgentStreamItem


class DummyAgent(Agent):
    """Dummy agent that always returns the same response text.

    Parameters
    ----------
    default_response : str, optional
        Response text yielded for every input turn.
    """

    def __init__(
        self,
        default_response: str = 'The term "psychology" can refer to the entirety of humans\' internal mental activities. It can also denote an organism\'s subjective reflection of the objective world, as well as the processes and phenomena related to mental activity, such as emotion, thinking, and behavior. In addition, "psychology" is often used to refer to the academic discipline that studies human psychological phenomena, mental functions, and behavior.',
    ) -> None:
        """Initialize the dummy agent."""
        self.default_response = default_response

    def generate_stream(
        self, input: Union[str, AgentInput]
    ) -> Iterable[AgentStreamItem]:
        """Yield the predefined response for the input turn.

        Parameters
        ----------
        input : str | AgentInput
            Input text or structured payload. Ignored by this implementation.

        Yields
        ------
        AgentStreamItem
            The configured response text as a single chunk.
        """

        del input
        yield self.default_response

    def restore_history(self, messages: list[dict[str, Any]]) -> None:
        """Ignore persisted history for the stateless dummy agent.

        Parameters
        ----------
        messages : list[dict[str, Any]]
            Persisted messages. Ignored by this implementation.
        """

        del messages
        return None

    def clone(self) -> "Agent":
        """Create a fresh dummy agent with the same canned response.

        Returns
        -------
        Agent
            Cloned dummy agent instance.
        """

        return DummyAgent(self.default_response)
