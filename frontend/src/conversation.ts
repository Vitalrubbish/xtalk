export { Conversation };
export type { ConversationMessage, ConversationState, ConversationUser };

type ConversationMessage = {
    role: "user" | "assistant" | "info";
    content: string;
    turnId?: number;
}

type ConversationUser = {
    id: string;
}

function defaultConversation(): {
    streamState: "idle" | "listening" | "processing" | "speaking";
    sessionId: string | null;
    user: ConversationUser | null;
    latency: {
        network?: number,
        asr?: number,
        llmFirstToken?: number,
        llmSentence?: number,
        ttsFirstChunk?: number
    };
    messages: ConversationMessage[];
    thought: string;
    caption: string;
    retrieval: string;
} {
    return {
        streamState: "idle",
        sessionId: null,
        user: null,
        latency: {},
        messages: [],
        thought: "",
        caption: "",
        retrieval: "",
    };
}

type ConversationState = ReturnType<typeof defaultConversation>;

class Conversation {
    private _state: ConversationState = defaultConversation();
    private stateChangeCallbacks = new Set<(state: ConversationState) => void>();
    private fullAudioChunkCallback: (pcmChunkInt16: ArrayBuffer, sampleRate: number) => void = (_chunk, _sr) => { };

    private notifyStateChange(): void {
        for (const callback of this.stateChangeCallbacks) {
            callback(this._state);
        }
    }

    onStateChange(callback: (state: ConversationState) => void): void {
        callback(this._state);
        this.stateChangeCallbacks.add(callback);
    }

    onFullAudioChunk(
        callback: (pcmChunkInt16: ArrayBuffer, sampleRate: number) => void
    ): void {
        this.fullAudioChunkCallback = callback;
    }

    get state(): ConversationState {
        return new Proxy(this._state, {
            set: (target, key: keyof ConversationState, value) => {
                target[key] = value;
                this.notifyStateChange();
                return true;
            },
            get: (target, key: keyof ConversationState) => {
                return key in target ? target[key] : undefined;
            }
        });
    }

    setUser(user: ConversationUser | null): void {
        this._state.user = user;
        this.notifyStateChange();
    }

    switch(sessionId: string | null, messages: ConversationMessage[]): void {
        this._state.sessionId = sessionId;
        this._state.messages = [...messages];
        this._state.streamState = "idle";
        this._state.thought = "";
        this._state.caption = "";
        this._state.retrieval = "";
        this._state.latency = {};
        this.notifyStateChange();
    }

    appendMessage(message: ConversationMessage): void {
        if (message.role === "info") {
            this._state.messages.push(message);
            this.notifyStateChange();
            return;
        }

        for (let i = this._state.messages.length - 1; i >= 0; i--) {
            const msg = this._state.messages[i]!;
            if (msg.role === message.role && msg.turnId === message.turnId) {
                msg.content = message.content;
                const lastMsg = this._state.messages[this._state.messages.length - 1];
                if (lastMsg && lastMsg.role === "info") {
                    this._state.messages.splice(this._state.messages.length - 1, 1);
                    this._state.messages.splice(i, 0, lastMsg);
                }
                this.notifyStateChange();
                return;
            }
        }

        this._state.messages.push(message);
        this.notifyStateChange();
    }

    updateLatency(latency: Conversation["state"]["latency"]): void {
        this._state.latency = { ...latency };
        this.notifyStateChange();
    }

    emitFullAudioChunk(pcmChunkInt16: ArrayBuffer, sampleRate: number): void {
        this.fullAudioChunkCallback(pcmChunkInt16, sampleRate);
    }
}
