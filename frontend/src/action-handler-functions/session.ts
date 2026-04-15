import type { ActionToFunctionMap } from "./types";
const sessionMap: ActionToFunctionMap = {
    "session_attached": async (data, websocket, conversation, outputAudioSession) => {
        const sid = data.session_id || null;
        if (conversation.state.sessionId !== sid) {
            conversation.switch(sid, []);
            return;
        }
        conversation.state.sessionId = sid;
    },
};

export default sessionMap;
