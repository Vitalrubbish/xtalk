import sys

from .utils import interfaces as interfaces
from .utils import runtime as runtime
from .utils import template as template
from .tools.utils import ToolCallResultArgs, ToolCallResultPayload
from .utils.interfaces import Agent, AgentContext, AgentInput
from .dummy import DummyAgent
from .default import DefaultAgent
from .utils.template import MutableToolProvider, TemplateAgent
from .utils.runtime import (
    AgentRequest,
    AgentRuntime,
    AgentSession,
    ContextAdapter,
    OutputPolicy,
    PromptBuilder,
    ScenarioSpec,
    TextChunkEvent,
    ToolCallEvent,
    ToolProvider,
    ToolResultEvent,
    TurnContext,
    TurnHook,
)

sys.modules[f"{__name__}.interfaces"] = interfaces
sys.modules[f"{__name__}.runtime"] = runtime
sys.modules[f"{__name__}.template"] = template

__all__ = [
    "Agent",
    "AgentContext",
    "AgentInput",
    "DummyAgent",
    "DefaultAgent",
    "TemplateAgent",
    "AgentRequest",
    "AgentRuntime",
    "AgentSession",
    "ContextAdapter",
    "MutableToolProvider",
    "OutputPolicy",
    "PromptBuilder",
    "ScenarioSpec",
    "TextChunkEvent",
    "ToolCallEvent",
    "ToolCallResultArgs",
    "ToolCallResultPayload",
    "ToolProvider",
    "ToolResultEvent",
    "TurnContext",
    "TurnHook",
]
