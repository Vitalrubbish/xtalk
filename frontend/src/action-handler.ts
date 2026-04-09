import { BaseWebSocket } from "./bases/websocket";
import { Conversation } from "./conversation";
import { BaseOutputAudioSession } from "./bases/audio-session";
import { ACTION_TO_FUNCTION } from "./action-handler-functions/index";
export { ActionHandler };


class ActionHandler {
    readonly ACTION_TO_FUNCTION = ACTION_TO_FUNCTION;
    private actionListeners = new Map<string, Set<() => void>>();

    waitForAction(action: string): Promise<void> {
        return new Promise((resolve) => {
            const listeners = this.actionListeners.get(action) ?? new Set<() => void>();
            const callback = () => {
                listeners.delete(callback);
                if (listeners.size === 0) {
                    this.actionListeners.delete(action);
                }
                resolve();
            };
            listeners.add(callback);
            this.actionListeners.set(action, listeners);
        });
    }

    private notifyActionHandled(action: string): void {
        const listeners = this.actionListeners.get(action);
        if (!listeners) {
            return;
        }
        for (const callback of [...listeners]) {
            callback();
        }
    }

    async handleAction(action: string, data: any, websocket: BaseWebSocket, conversation: Conversation, outputAudioSession: BaseOutputAudioSession) {
        const handler = this.ACTION_TO_FUNCTION[action];
        if (handler) {
            await handler(data, websocket, conversation, outputAudioSession);
            this.notifyActionHandled(action);
        } else {
            throw new Error(`No handler found for action: ${action}`);
        }
    }
}
