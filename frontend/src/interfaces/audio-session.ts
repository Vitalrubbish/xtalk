export { IInputAudioSession, IOutputAudioSession };

abstract class IInputAudioSession {
    abstract open(): Promise<void>;
    abstract close(): Promise<void>;
    abstract get muted(): boolean;
    abstract set muted(value: boolean);

    onFrame(callback: (pcm_chunk_int16: ArrayBuffer) => void) {
        this.frameCallback = callback;
    }
    onSpeechStart(callback: () => void) {
        this.speechStartCallback = callback;
    }
    onSpeechEnd(callback: () => void) {
        this.speechEndCallback = callback;
    }
    protected frameCallback(pcm_chunk_int16: ArrayBuffer) {

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

abstract class IOutputAudioSession {
    abstract open(): Promise<void>;
    abstract close(): Promise<void>;
    abstract pause(): Promise<void>;
    abstract resume(): Promise<void>;
    abstract stop(): Promise<void>;
    abstract push_audio(pcm_chunk_int16: ArrayBuffer): void;

    onChunkPlayed(callback: () => void) {
        this.chunkPlayedCallback = callback;
    }
    onAllChunksPlayed(callback: () => void) {
        this.allChunksPlayedCallback = callback;
    }
    protected chunkPlayedCallback() {

    }
    protected allChunksPlayedCallback() {

    }
}