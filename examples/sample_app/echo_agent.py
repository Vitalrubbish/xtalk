from typing import Iterable

from xtalk.model_types import Agent


class EchoAgent(Agent):
    """A simple agent that echoes user input."""

    def generate_stream(self, input) -> Iterable[str]:
        if isinstance(input, dict):
            yield input["content"]
            return
        yield input

    def clone(self) -> "EchoAgent":
        return EchoAgent()
