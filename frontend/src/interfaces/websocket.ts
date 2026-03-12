export { IWebSocket };
type WebSocketEventType = 'open' | 'message' | 'close' | 'error';
abstract class IWebSocket {
    abstract ready(): boolean;

    abstract send(data: string | ArrayBuffer): void;

    abstract close(): void;

    abstract addEventListener(type: WebSocketEventType, listener: (evt?: any) => any): void;
}