import type { ActionToFunctionMap } from "./types";
const messagesMap: ActionToFunctionMap = {
    "session_info": async (data, websocket, conversation, outputAudioSession) => {
        const sid = data.session_id || null;
        conversation.state.currentSessionId = sid;
    },
};

export default messagesMap;
