interface IWebSocket {
    ready(): boolean;
    send(data: string | ArrayBuffer): void;
    close(): void;
    addEventListener(type: string, listener: (evt: any) => void): void;
}