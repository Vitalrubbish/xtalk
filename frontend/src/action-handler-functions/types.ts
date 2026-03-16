import { BaseWebSocket } from "../bases/websocket";
import { Conversation } from "../conversation";
import { BaseOutputAudioSession } from "../bases/audio-session";
export type { ActionToFunctionMap };
type ActionHandlerFunction = (data: any, websocket: BaseWebSocket, conversation: Conversation, outputAudioSession: BaseOutputAudioSession) => Promise<void>;
type ActionToFunctionMap = Record<string, ActionHandlerFunction>;