export { IInputAudioSession, IOutputAudioSession };

abstract class IInputAudioSession {
    abstract start(): Promise<void>;
    abstract stop(): Promise<void>;
    abstract get muted(): boolean;
    abstract set muted(value: boolean);

    onFrame(pcm_chunk_int16: ArrayBuffer) {

    };
    /**
     * Used only when VAD enabled
     */
    onSpeechStart() {

    };
    /**
     * Used only when VAD enabled
     */
    onSpeechEnd() {

    };
}

abstract class IOutputAudioSession {
    abstract push_audio(pcm_chunk_int16: ArrayBuffer): void;
    abstract pause(): Promise<void>;
    abstract resume(): Promise<void>;
    abstract start(): Promise<void>;
    abstract stop(): Promise<void>;
}