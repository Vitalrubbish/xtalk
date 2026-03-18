import asyncio
import uuid
import base64
import json
from typing import Optional, Literal

import numpy as np
import websockets

from ..interfaces import (
    TurnDetector,
    TurnDetectionAction,
    TurnDetectionResult,
    TurnDetectionSemantic,
)

_IDLE_RESULT = TurnDetectionResult(
    action=TurnDetectionAction.DO_NOTHING,
    semantic=TurnDetectionSemantic.IDLE,
)


class SoulxDuplug(TurnDetector):
    """Turn detector backed by the SoulX duplex turn-taking WebSocket service."""

    def __init__(
        self,
        server_url: str = "ws://localhost:8000/turn",
        client_id: Optional[str] = None,
        timeout: float = 1.0,
    ) -> None:
        self._server_url = server_url
        self._client_id = client_id or uuid.uuid4().hex
        self._timeout = timeout
        self._ws: Optional[websockets.ClientConnection] = None
        self._listening = True
        self._listening_lock = asyncio.Lock()

    async def _connect(self) -> None:
        self._ws = await websockets.connect(self._server_url)

    async def _send_audio(self, audio: bytes) -> dict:
        """Send audio to the server and return the parsed response."""
        pcm = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        payload = {
            "type": "audio",
            "session_id": self._client_id,
            "audio": base64.b64encode(pcm.astype(np.float32).tobytes()).decode(),
        }
        msg = json.dumps(payload)

        try:
            await self._ws.send(msg)
            response = await asyncio.wait_for(self._ws.recv(), timeout=self._timeout)
            return json.loads(response)
        except Exception:
            # Reconnect on any failure and retry once
            await self._connect()
            await self._ws.send(msg)
            response = await asyncio.wait_for(self._ws.recv(), timeout=self._timeout)
            return json.loads(response)

    def detect(
        self,
        audio: Optional[bytes] = None,
        text: Optional[str] = None,
        speech_pause: Optional[bool] = None,
    ) -> TurnDetectionResult | list[TurnDetectionResult]:
        return asyncio.run(self.async_detect(audio, text, speech_pause))

    async def async_detect(
        self,
        audio: Optional[bytes] = None,
        text: Optional[str] = None,
        speech_pause: Optional[bool] = None,
    ) -> TurnDetectionResult | list[TurnDetectionResult]:
        if audio is None:
            return _IDLE_RESULT

        if self._ws is None:
            await self._connect()

        data = await self._send_audio(audio)
        state_name: Literal["idle", "nonidle", "speak", "blank"] = data.get(
            "state", {}
        ).get("state", "blank")

        # Concrete logic
        async with self._listening_lock:
            if self._listening:
                if state_name == "speak":
                    self._listening = False
                    return TurnDetectionResult(
                        action=TurnDetectionAction.START_GENERATION,
                        semantic=TurnDetectionSemantic.COMPLETE,
                    )
                if state_name == "nonidle":
                    return TurnDetectionResult(
                        action=TurnDetectionAction.DO_NOTHING,
                        semantic=TurnDetectionSemantic.INCOMPLETE,
                    )
            else:
                if state_name == "nonidle":
                    self._listening = True
                    return TurnDetectionResult(
                        action=TurnDetectionAction.STOP_SPEAKING,
                        semantic=TurnDetectionSemantic.INCOMPLETE,
                    )
        return _IDLE_RESULT

    def clone(self) -> "SoulxDuplug":
        return SoulxDuplug(
            server_url=self._server_url,
            timeout=self._timeout,
        )
