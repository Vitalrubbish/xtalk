import type { ActionToFunctionMap } from "./types";
const clientOperationMap: ActionToFunctionMap = {
    "client_change_voice": async (data, websocket, conversation, outputAudioSession) => {
        websocket.sendJson({
            action: "change_voice",
            voice_name: data.voiceName,
        })
    },
};

export default clientOperationMap;
