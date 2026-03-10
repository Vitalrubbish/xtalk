interface IWebSocket {
    ready(): boolean;

    send(data: string | ArrayBuffer): void;

    close(): void;

    addEventListener(type: 'open', listener: (evt: Event) => void): void;
    addEventListener(type: 'message', listener: (evt: MessageEvent) => void): void;
    addEventListener(type: 'close', listener: (evt: CloseEvent) => void): void;
    addEventListener(type: 'error', listener: (evt: Event) => void): void;
}