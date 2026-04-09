export { BaseHTTPClient, HTTPRequestError };
export type { ResolvableURL, SessionServiceURLConfig, SessionServiceURLs };

type ResolvableURL = string | URL;

type SessionServiceURLConfig = Partial<{
    login: ResolvableURL;
    sessions: ResolvableURL;
    sessionDetail: ResolvableURL | ((sessionId: string) => ResolvableURL);
    upload: ResolvableURL;
}>;

type SessionServiceURLs = {
    login: ResolvableURL;
    sessions: ResolvableURL;
    sessionDetail(sessionId: string): ResolvableURL;
    upload: ResolvableURL;
}

abstract class BaseHTTPClient {
    abstract postJSON<T>(url: ResolvableURL, accessToken: string | null): Promise<T>;
    abstract getJSON<T>(url: ResolvableURL, accessToken: string): Promise<T>;
    abstract postFile(url: ResolvableURL, accessToken: string, sessionId: string, file: Blob): Promise<void>;
}

class HTTPRequestError extends Error {
    readonly status: number;

    constructor(status: number, message?: string) {
        super(message ?? `Request failed with status ${status}`);
        this.name = "HTTPRequestError";
        this.status = status;
    }
}
