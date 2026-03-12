import { Conversation } from "./conversation";
import { BaseOutputAudioSession } from "./bases/audio-session";

export { ActionHandler };

class ActionHandler {
    readonly ACTION_TO_HANDLER: { [key: string]: (data: any, conversation: Conversation, outputAudioSession: BaseOutputAudioSession) => void } = {};
    handleAction(action: string, data: any, conversation: Conversation, outputAudioSession: BaseOutputAudioSession) {
        if (action in this.ACTION_TO_HANDLER) {
            this.ACTION_TO_HANDLER[action]!(data, conversation, outputAudioSession);
        } else {
            console.warn(`No handler for action: ${action}`);
        }
    }
}