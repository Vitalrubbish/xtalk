import type { ActionToFunctionMap } from "./types";
const clientMap: ActionToFunctionMap = {
    "client_speech_start": (data, websocket, conversation, outputAudioSession) => {
        conversation.state.streamState = 'listening';
    },
    "client_speech_end": (data, websocket, conversation, outputAudioSession) => {
        conversation.state.streamState = 'processing';
    },
    "client_audio_chunk_started": (data, websocket, conversation, outputAudioSession) => {
        conversation.state.streamState = 'speaking';
    },
    "client_audio_playback_finished": (data, websocket, conversation, outputAudioSession) => {
        conversation.state.streamState = 'idle';
    },
    "client_audio_chunk_played": (data, websocket, conversation, outputAudioSession) => {
        websocket.sendJson({ action: "tts_chunk_played" })
    }
};

export default clientMap;
