import { Conversation } from "./conversation";
import { BaseOutputAudioSession } from "./bases/audio-session";
import { ACTION_TO_FUNCTION } from "./action-handler-functions/index";
export { ActionHandler };


class ActionHandler {
    readonly ACTION_TO_FUNCTION = ACTION_TO_FUNCTION;
    handleAction(action: string, data: any, conversation: Conversation, outputAudioSession: BaseOutputAudioSession) {
        const handler = this.ACTION_TO_FUNCTION[action];
        if (handler) {
            handler(data, conversation, outputAudioSession);
        } else {
            throw new Error(`No handler found for action: ${action}`);
        }
    }
}