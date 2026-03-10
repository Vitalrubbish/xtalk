export type { IInputAudioSession, IOutputAudioSession };

interface IInputAudioSession {
    start(): Promise<void>;
    stop(): Promise<void>;
    get muted(): boolean;
    set muted(value: boolean);

    onFrame(pcm_chunk_int16: ArrayBuffer): void;
}

interface IOutputAudioSession {
    push_audio(pcm_chunk_int16: ArrayBuffer): void;
    pause(): Promise<void>;
    resume(): Promise<void>;
    start(): Promise<void>;
    stop(): Promise<void>;
}