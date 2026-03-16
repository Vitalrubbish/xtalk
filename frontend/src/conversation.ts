export { Conversation };

function defaultConversation(): {
    streamState: "idle" | "listening" | "processing" | "speaking";
    currentSessionId: string | null;
} {
    return {
        streamState: "idle",
        currentSessionId: null
    };
}
type ConversationState = ReturnType<typeof defaultConversation>;
class Conversation {
    private _state: ConversationState = defaultConversation();
    private stateChangeCallback: (state: ConversationState) => void = () => { };
    onStateChange(callback: (state: ConversationState) => void): void {
        callback(this._state);
        this.stateChangeCallback = callback;
    }
    get state(): ConversationState {
        return new Proxy(this._state, {
            set: (target, key: keyof ConversationState, value) => {
                target[key] = value;
                this.stateChangeCallback(target);
                return true;
            },
            get: (target, key: keyof ConversationState) => {
                return key in target ? target[key] : undefined;
            }
        });
    }
}