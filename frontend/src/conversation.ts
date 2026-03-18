export { Conversation };

type Message = {
    role: "user" | "assistant" | "info";
    content: string;
    turnId?: number;
}
function defaultConversation(): {
    streamState: "idle" | "listening" | "processing" | "speaking";
    sessionId: string | null;
    messages: Message[];
    thought: string;
    caption: string;
    retrieval: string;
} {
    return {
        streamState: "idle",
        sessionId: null,
        messages: [],
        thought: "",
        caption: "",
        retrieval: "",
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
    appendMessage(message: Message): void {
        // If is an info, directly append
        if (message.role === "info") {
            this.state.messages.push(message);
            this.stateChangeCallback(this._state);
            return;
        }
        // Find the latest message with same role and turnId to replace
        for (let i = this.state.messages.length - 1; i >= 0; i--) {
            const msg = this.state.messages[i]!;
            if (msg.role === message.role && msg.turnId === message.turnId) {
                msg.content = message.content;
                // If last message is an info, put that message in front of the updated message
                const lastMsg = this.state.messages[this.state.messages.length - 1]!;
                if (lastMsg.role === "info") {
                    this.state.messages.splice(this.state.messages.length - 1, 1);
                    this.state.messages.splice(i, 0, lastMsg);
                }
                this.stateChangeCallback(this._state);
                return;
            }
        }
        // Otherwise, add as new message
        this.state.messages.push(message);
        this.stateChangeCallback(this._state);

    }
}