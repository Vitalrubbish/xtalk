interface IInputAudioContext {
    start(): Promise<void>;
    stop(): Promise<void>;
    get muted(): boolean;
    set muted(value: boolean);
}