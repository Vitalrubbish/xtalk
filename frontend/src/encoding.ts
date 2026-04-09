import { BaseEncoding } from "./bases/encoding";
import { getPlatformRuntime } from "./platforms/index";

export { createEncoding };

function createEncoding(): BaseEncoding {
    return getPlatformRuntime().createEncoding();
}
