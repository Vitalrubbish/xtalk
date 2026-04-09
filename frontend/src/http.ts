import { BaseHTTPClient } from "./bases/http";
import type { ResolvableURL, SessionServiceURLConfig, SessionServiceURLs } from "./bases/http";
import { getPlatformRuntime } from "./platforms/index";

export { createHTTPClient, buildAuthenticatedWebSocketURL, resolvePlatformServiceURLs };

function createHTTPClient(): BaseHTTPClient {
    return getPlatformRuntime().createHTTPClient();
}

function resolvePlatformServiceURLs(
    websocketURL: ResolvableURL,
    config?: SessionServiceURLConfig,
): SessionServiceURLs {
    return getPlatformRuntime().resolveServiceURLs(websocketURL, config);
}

function buildAuthenticatedWebSocketURL(
    websocketURL: ResolvableURL,
    accessToken: string,
): ResolvableURL {
    return getPlatformRuntime().buildAuthenticatedWebSocketURL(
        websocketURL,
        accessToken,
    );
}
