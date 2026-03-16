export { Conversation };

interface ConversationState {
    streamState: "idle" | "listening" | "processing" | "speaking";
}
class Conversation {
    private _state: ConversationState = {
        streamState: "idle"
    };
    private stateChangeCallback: (state: ConversationState) => void = () => { };
    onStateChange(callback: (state: ConversationState) => void): void {
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