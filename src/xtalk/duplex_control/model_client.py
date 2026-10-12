"""Stream raw ChatML completions from the official-weight inference service."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import AsyncIterator

import aiohttp


@dataclass(frozen=True)
class GenerationEnd:
    """Preserve the model service's stop or token-budget termination reason."""

    reason: str


class DuplexModelClient:
    """Send raw prompts while preserving all conversational special tokens.

    Parameters
    ----------
    base_url : str
        Official-weight service root.
    max_new_tokens : int
        Per system micro-turn generation limit (official default 64).
    timeout_seconds : float
        Request deadline; generation errors propagate to the runtime.
    """

    def __init__(self, base_url: str, max_new_tokens: int = 64, timeout_seconds: float = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_new_tokens = max_new_tokens
        self.timeout_seconds = timeout_seconds

    async def stream(self, prompt: str) -> AsyncIterator[str | GenerationEnd]:
        """Yield NDJSON token text, including special and end-of-message tokens.

        Parameters
        ----------
        prompt : str
            Complete raw ChatML micro-turn history and assistant header.
        """
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.base_url + "/generate", json={
                "prompt": prompt, "max_new_tokens": self.max_new_tokens,
            }) as response:
                response.raise_for_status()
                async for line in response.content:
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise RuntimeError("Malformed NDJSON from official model service") from exc
                    if "error" in payload:
                        raise RuntimeError(payload["error"])
                    if "text" in payload:
                        yield payload["text"]
                    if "finish_reason" in payload:
                        yield GenerationEnd(payload["finish_reason"])
