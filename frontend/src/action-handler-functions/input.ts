import type { ActionToFunctionMap } from "./types";
import { onVadSpeechStart, onVadSpeechEnd } from "./utils";
import { createEncoding } from "../encoding";

const encoding = createEncoding();

const inputMap: ActionToFunctionMap = {
    "vad_speech_start": async (data, websocket, conversation, outputAudioSession) => {
        onVadSpeechStart(data, websocket, conversation, outputAudioSession);
    },
    "vad_speech_end": async (data, websocket, conversation, outputAudioSession) => {
        onVadSpeechEnd(data, websocket, conversation, outputAudioSession);
    },
    "full_audio_frame": async (data, websocket, conversation, outputAudioSession) => {
        const audioBase64 = typeof data?.audio_base64 === "string" ? data.audio_base64 : "";
        if (!audioBase64) {
            return;
        }
        const sampleRate = typeof data?.sample_rate === "number" ? data.sample_rate : 48000;
        const pcmChunkInt16 = encoding.decodeBase64(audioBase64);
        conversation.emitFullAudioChunk(pcmChunkInt16, sampleRate);
    }
};

export default inputMap;
