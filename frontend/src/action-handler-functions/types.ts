import { Conversation } from "../conversation";
import { BaseOutputAudioSession } from "../bases/audio-session";
export type { ActionHandlerFunction, ActionToFunctionMap };
type ActionHandlerFunction = (data: any, conversation: Conversation, outputAudioSession: BaseOutputAudioSession) => void;
type ActionToFunctionMap = Record<string, ActionHandlerFunction>;