export { BaseEncoding };

abstract class BaseEncoding {
    abstract decodeBase64(base64: string): ArrayBuffer;
}
