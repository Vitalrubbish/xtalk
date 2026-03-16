export { BaseInputAudioSession, BaseOutputAudioSession };

abstract class BaseInputAudioSession {
    abstract open(): Promise<void>;
    abstract close(): Promise<void>;
    abstract get muted(): boolean;
    abstract set muted(value: boolean);

    onFrame(callback: (pcmChunkInt16: ArrayBuffer) => void) {
        this.frameCallback = callback;
    }
    onSpeechStart(callback: () => void) {
        this.speechStartCallback = callback;
    }
    onSpeechEnd(callback: () => void) {
        this.speechEndCallback = callback;
    }
    protected frameCallback(_pcmChunkInt16: ArrayBuffer) {

    };
    /**
     * Used only when VAD enabled
     */
    protected speechStartCallback() {

    };
    /**
     * Used only when VAD enabled
     */
    protected speechEndCallback() {

    };
}

abstract class BaseOutputAudioSession {
    abstract open(): Promise<void>;
    abstract close(): Promise<void>;
    abstract pause(): Promise<void>;
    abstract resume(): Promise<void>;
    abstract stop(): Promise<void>;
    abstract pushAudioChunk(pcmChunkInt16: ArrayBuffer): Promise<void>;

    onChunkStarted(callback: (pcmChunkInt16: ArrayBuffer) => void) {
        this.chunkStartedCallback = callback;
    }
    onChunkPlayed(callback: (pcmChunkInt16: ArrayBuffer) => void) {
        this.chunkPlayedCallback = callback;
    }
    onAllChunksPlayed(callback: () => void) {
        this.allChunksPlayedCallback = callback;
    }
    protected chunkStartedCallback(_pcmChunkInt16: ArrayBuffer) {

    }
    protected chunkPlayedCallback(_pcmChunkInt16: ArrayBuffer) {

    }
    protected allChunksPlayedCallback() {

    }
}