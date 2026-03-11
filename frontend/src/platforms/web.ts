import { IInputAudioSession, IOutputAudioSession } from "../interfaces/audio";

import vadProcessorUrl from "../worklets/vad-processor.worklet.js";

interface Window {
    ort?: any
    vad?: any
}
interface WebInputAudioSessionCore {
    audioContext: AudioContext;
    sourceNode: MediaStreamAudioSourceNode;
    framePreprocessNode: AudioWorkletNode;
    silentGainNode: GainNode;
    inputStream: MediaStream;
}
class WebInputAudioSession extends IInputAudioSession {
    readonly VAD_PARAMS = {
        vadFrameSamples: 512,
        vadNegativeFramesBeforeEnd: 50,
        vadConfig: {
            positiveSpeechThreshold: 0.8,
            negativeSpeechThreshold: 0.2,
            preSpeechPadMs: 30,
            redemptionMs: 500,
            minSpeechMs: 250,
            submitUserSpeechOnPause: false
        }
    }
    private _muted = false;
    private session: WebInputAudioSessionCore | null = null;
    constructor(private sampleRate: number = 16000) {
        super()
    }
    async start(): Promise<void> {
        if (this.session !== null) {
            throw new Error('Session already started');
        }
        const audioContext = new window.AudioContext({ sampleRate: this.sampleRate })
        // Prepare input stream
        const inputStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                channelCount: 1,
                echoCancellation: true,
                autoGainControl: true,
                noiseSuppression: false
            }
        });
        const sourceNode = audioContext.createMediaStreamSource(inputStream);
        // Prepare frame processor
        // VAD states
        const vadURL = 'https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.27/dist/silero_vad_v5.onnx';
        const vadArrayBuffer = await fetch(vadURL).then(r => r.arrayBuffer());
        const vadSession = await window.ort.InferenceSession.create(vadArrayBuffer);
        const vadStateZeros = Array(2 * 128).fill(0);
        let vadState = new window.ort.Tensor('float32', vadStateZeros, [2, 1, 128]);
        const vadSr = new window.ort.Tensor('int64', [BigInt(this.sampleRate)]);
        const vadHelpers = {
            negEndCounterEnabled: false,
            negEndCounter: 0
        }

        await this.ensureModelsEnv();
        await audioContext.audioWorklet.addModule(vadProcessorUrl);
        const framePreprocessNode = new AudioWorkletNode(audioContext, 'vad-processor', {
            processorOptions: {
                targetSampleRate: this.sampleRate,
                targetFrameSize: this.VAD_PARAMS.vadFrameSamples
            }
        })
        const enhanceFrame = async (frame: Float32Array) => {
            // TODO
            return frame;
        }
        const frameProcessorProcess = async (frame: Float32Array) => {
            const enhancedFrame = await enhanceFrame(frame);
            const audioTensor = new window.ort.Tensor('float32', enhancedFrame, [1, enhancedFrame.length]);
            const inputs = { input: audioTensor, vadState, vadSr };
            const out = await vadSession.run(inputs);
            vadState = out.stateN;
            const isSpeech = out.output.data[0];
            return { isSpeech, notSpeech: 1 - isSpeech };
        }
        const frameProcessorReset = () => {
            vadState = new window.ort.Tensor('float32', vadStateZeros, [2, 1, 128]);
            // TODO: enhancer reset
        }
        const frameProcessor = new window.vad.FrameProcessor(
            frameProcessorProcess,
            frameProcessorReset,
            this.VAD_PARAMS.vadConfig,
            this.VAD_PARAMS.vadFrameSamples / this.sampleRate * 1000
        )
        const onFrameProcessorEvent = (ev: { msg: any; frame: Float32Array; probs: { notSpeech: number; }; }) => {
            switch (ev.msg) {
                case window.vad.Message.FrameProcessed:
                    const frame = ev.frame; // Original frame from input
                    // Use consecutive notSpeech samples to trigger early speech end
                    if (vadHelpers.negEndCounterEnabled) {
                        const ns = Number(ev?.probs?.notSpeech ?? 0);
                        const nsHigh = ns > (1 - this.VAD_PARAMS.vadConfig.negativeSpeechThreshold);
                        vadHelpers.negEndCounter = nsHigh ? (vadHelpers.negEndCounter + 1) : 0;
                        if (vadHelpers.negEndCounter > this.VAD_PARAMS.vadNegativeFramesBeforeEnd) {
                            // Trigger speech end and disable/reset the counter
                            this.onSpeechEnd();
                            vadHelpers.negEndCounterEnabled = false;
                            vadHelpers.negEndCounter = 0;
                        }
                    }
                    // const enhancedFrame = lastEnhancedFrame || frame; // Use enhanced frame if available

                    // Only trigger frame event to the backend when not muted
                    if (!this.muted) {
                        this.onFrame(frame);
                    }
                    break;

                case window.vad.Message.SpeechStart:
                    this.onSpeechStart();

                    // Enable the negative sample counter when speech starts
                    vadHelpers.negEndCounterEnabled = true;
                    vadHelpers.negEndCounter = 0;

                    break;

                case window.vad.Message.SpeechEnd:
                    this.onSpeechEnd();

                    // Disable/reset the counter when VAD reports speech end
                    vadHelpers.negEndCounterEnabled = false;
                    vadHelpers.negEndCounter = 0;
                    break;
            }
        };
        const frameQueue: Float32Array[] = [];
        let isProcessingFrameQueue: boolean = false;
        framePreprocessNode.port.onmessage = async (event) => {
            // See frontend/worklets/vad-processor.worklet.js for data fields
            if (event.data.type === 'audioFrame') {
                if (this.muted) return;
                frameQueue.push(event.data.frame);
                // Process frames
                if (isProcessingFrameQueue) return;
                isProcessingFrameQueue = true;
                while (frameQueue.length > 0) {
                    const frame = frameQueue.shift();
                    await frameProcessor.process(frame, onFrameProcessorEvent);
                }
                isProcessingFrameQueue = false;
            }
        }
        // Connect nodes
        const silentGainNode = audioContext.createGain();
        silentGainNode.gain.value = 0;
        sourceNode.connect(framePreprocessNode);
        framePreprocessNode.connect(silentGainNode);
        silentGainNode.connect(audioContext.destination);

        // Start processing
        frameProcessor.resume();

        // Mount to session to keep alive local vars and for later clean up
        this.session = {
            audioContext,
            sourceNode,
            framePreprocessNode,
            silentGainNode,
            inputStream,
        }
    }
    async stop(): Promise<void> {
        if (!this.session) return;
        this.session.sourceNode.disconnect();
        this.session.framePreprocessNode.disconnect();
        this.session.silentGainNode.disconnect();
        this.session.audioContext.close();
        this.session.inputStream.getAudioTracks().forEach(track => track.stop());
        this.session = null;
    }

    get muted(): boolean {
        return this._muted;
    }
    set muted(value: boolean) {
        this._muted = value;
    }

    private async ensureModelsEnv() {
        // Inject window.ort and window.vad
        const inject = (src: string) => new Promise<void>((resolve, reject) => {
            const s = document.createElement('script');
            s.src = src;
            s.onload = () => resolve();
            s.onerror = (e) => reject(e);
            document.head.appendChild(s);
        });
        if (!window.ort) {
            // Pick ORT version by UA (only iOS stays on 1.17.0)
            const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent);
            const ortVersion = isIOS ? '1.17.0' : '1.22.0';

            await inject(`https://cdn.jsdelivr.net/npm/onnxruntime-web@${ortVersion}/dist/ort.js`);
            window.ort.env.wasm.wasmPaths = `https://cdn.jsdelivr.net/npm/onnxruntime-web@${ortVersion}/dist/`;
        }
        if (!window.vad) {
            await inject('https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.27/dist/bundle.min.js');
        }
    }
}