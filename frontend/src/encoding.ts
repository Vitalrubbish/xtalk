import { getPlatform, Platform } from "./utils";
import { BaseEncoding } from "./bases/encoding";
import { WebEncoding } from "./platforms/web";

export { createEncoding };

function createEncoding(): BaseEncoding {
    switch (getPlatform()) {
        case Platform.Web:
            return new WebEncoding();
        default:
            throw new Error("Unknown platform");
    }
}
