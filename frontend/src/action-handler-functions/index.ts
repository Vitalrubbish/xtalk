import type { ActionHandlerFunction, ActionToFunctionMap } from "./types";
export { ACTION_TO_FUNCTION };

const ACTION_TO_FUNCTION: ActionToFunctionMap = {}

function registerMap(partial_map: ActionToFunctionMap) {
    for (const key in partial_map) {
        if (partial_map[key]) {
            ACTION_TO_FUNCTION[key] = partial_map[key];
        }
    }
}

// ------------ Import and register action handler functions here ------------