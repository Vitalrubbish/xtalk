export { Platform, getPlatform }

enum Platform {
    Web
}

function getPlatform(): Platform {
    if (typeof window !== "undefined" &&
        typeof document !== "undefined")
        return Platform.Web;
    throw new Error("Unknown platform");
}