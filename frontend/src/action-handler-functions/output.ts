import type { ActionToFunctionMap } from "./types";
const outputMap: ActionToFunctionMap = {
    "start_tts": (data, websocket, conversation, outputAudioSession) => {
        // Leave blank, no use
    },
    "pause_tts": (data, websocket, conversation, outputAudioSession) => {
        outputAudioSession.pause();
    },
    "stop_tts": (data, websocket, conversation, outputAudioSession) => {
        outputAudioSession.stop();
    },
    "resume_tts": (data, websocket, conversation, outputAudioSession) => {
        outputAudioSession.resume();
    },
};

export default outputMap;
