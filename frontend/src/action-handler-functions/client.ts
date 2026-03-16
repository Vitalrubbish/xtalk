import type { ActionToFunctionMap } from "./types";
const clientMap: ActionToFunctionMap = {
    "client_speech_start": (data, websocket, conversation, outputAudioSession) => {
        conversation.state.streamState = 'listening';
        websocket.sendJson({ action: "vad_speech_start" })
    },
    "client_speech_end": (data, websocket, conversation, outputAudioSession) => {
        conversation.state.streamState = 'processing';
        websocket.sendJson({ action: "vad_speech_end" })
    },
    "client_audio_chunk_started": (data, websocket, conversation, outputAudioSession) => {
        conversation.state.streamState = 'speaking';
    },
    "client_audio_playback_finished": (data, websocket, conversation, outputAudioSession) => {
        conversation.state.streamState = 'idle';
        websocket.sendJson({ action: "tts_playback_finished" })
    },
    "client_audio_chunk_played": (data, websocket, conversation, outputAudioSession) => {
        websocket.sendJson({ action: "tts_chunk_played" })
    }
};

export default clientMap;
