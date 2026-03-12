export { Conversation };

interface ConversationState {
    [key: string]: any;
}
class Conversation {
    private _state: ConversationState = {};
    private stateChangeCallback: (state: ConversationState) => void = () => { };
    onStateChange(callback: (state: ConversationState) => void): void {
        this.stateChangeCallback = callback;
    }
    get state(): ConversationState {
        return new Proxy(this._state, {
            set: (target, key: any, value) => {
                target[key] = value;
                this.stateChangeCallback(target);
                return true;
            },
            get: (target, key: any) => {
                return key in target ? target[key] : undefined;
            }
        });
    }
}