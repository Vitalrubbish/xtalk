import asyncio
import uuid
import base64
import json
from typing import Optional

import numpy as np
import websocket

from ..interfaces import (
    TurnDetector,
    TurnDetectionAction,
    TurnDetectionResult,
    TurnDetectionSemantic,
)

from typing import Literal

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
        self._ws: Optional[websocket.WebSocket] = None
        self._listening = True
        self._listening_lock = asyncio.Lock()

    def _connect(self) -> None:
        self._ws = websocket.create_connection(self._server_url)
        self._ws.settimeout(self._timeout)

    def _send_audio(self, audio: bytes) -> dict:
        """Send audio to the server and return the parsed response."""
        # Convert raw PCM 16-bit mono 16kHz bytes to float32
        pcm = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        payload = {
            "type": "audio",
            "session_id": self._client_id,
            "audio": base64.b64encode(pcm.astype(np.float32).tobytes()).decode(),
        }
        msg = json.dumps(payload)

        try:
            self._ws.send(msg)
            response = self._ws.recv()
            return json.loads(response)
        except Exception:
            # Reconnect on any failure and retry once
            self._connect()
            self._ws.send(msg)
            response = self._ws.recv()
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
            self._connect()

        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, self._send_audio, audio)
        state_name: Literal["idle", "nonidle", "speak", "blank"] = data.get(
            "state", {}
        ).get("state", "blank")

        if state_name == "speak":
            return TurnDetectionResult(
                action=TurnDetectionAction.START_GENERATION,
                semantic=TurnDetectionSemantic.COMPLETE,
            )
        if state_name == "nonidle":
            return TurnDetectionResult(
                action=TurnDetectionAction.DO_NOTHING,
                semantic=TurnDetectionSemantic.INCOMPLETE,
            )
        # idle / blank / unknown
        return _IDLE_RESULT

    def clone(self) -> "SoulxDuplug":
        return SoulxDuplug(
            server_url=self._server_url,
            timeout=self._timeout,
        )
