import { BaseWebSocket } from "./bases/websocket";
import { getPlatformRuntime } from "./platforms/index";
export { createWebSocket };

function createWebSocket(url: string | URL, protocols?: string | string[]): BaseWebSocket {
    return getPlatformRuntime().createWebSocket(url, protocols);
}
