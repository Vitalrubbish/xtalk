"""Select the single DuplexCascade control path for an X-Talk session."""

from __future__ import annotations

from xtalk.serving.interfaces import Manager
from .micro_turn import MicroTurnAssembler
from .runtime_adapter import DuplexRuntimeAdapter


def duplex_manager_classes(classes: list[type[Manager]]) -> list[type[Manager]]:
    """Keep native ASR/TTS/playback and replace semantic control managers.

    Parameters
    ----------
    classes : list[type[Manager]]
        Manager classes configured by the calling service.

    Returns
    -------
    list[type[Manager]]
        Ordered manager set with exactly one assembler and runtime adapter.
    """
    from xtalk.serving.modules.llm_agent_context_manager import LLMAgentContextManager
    from xtalk.serving.modules.llm_agent_generation_manager import LLMAgentConsumptionManager
    from xtalk.serving.modules.turn_taking_manager import TurnTakingManager
    from xtalk.serving.modules.turn_detector_manager import TurnDetectorManager
    from xtalk.serving.modules.multi_speaker_turn_context_manager import MultiSpeakerTurnContextManager
    from xtalk.serving.modules.direct_audio_manager import DirectAudioManager

    replaced = (LLMAgentContextManager, LLMAgentConsumptionManager, TurnTakingManager,
                TurnDetectorManager, MultiSpeakerTurnContextManager, DirectAudioManager,
                MicroTurnAssembler, DuplexRuntimeAdapter)
    return [MicroTurnAssembler, DuplexRuntimeAdapter] + [
        item for item in classes if not issubclass(item, replaced)
    ]
