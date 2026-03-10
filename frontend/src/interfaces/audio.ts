interface IInputAudioSession {
    start(): Promise<void>;
    stop(): Promise<void>;
    get muted(): boolean;
    set muted(value: boolean);
}

interface IOutputAudioSession {
    push_audio(chunk: ArrayBuffer): void;
    pause(): Promise<void>;
    resume(): Promise<void>;
    start(): Promise<void>;
    stop(): Promise<void>;
}