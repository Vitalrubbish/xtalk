import type { ActionToFunctionMap } from "./types";
const metaMap: ActionToFunctionMap = {
    "thought_updated": async (data, websocket, conversation, outputAudioSession) => {
        conversation.state.thought = data.text;
    },
    "caption_updated": async (data, websocket, conversation, outputAudioSession) => {
        conversation.state.caption = data.text;
    },
    "retrieval_updated": async (data, websocket, conversation, outputAudioSession) => {
        conversation.state.retrieval = data.text;
    },
    "tool_called": async (data, websocket, conversation, outputAudioSession) => {
        conversation.state.tool_call = {
            name: data.name,
            args: data.args || {}
        };
    }
};

export default metaMap;
