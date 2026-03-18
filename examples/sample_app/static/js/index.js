async function loadXtalk() {
    try {
        console
        return await import("../../xtalk/index.js");
    } catch (e) {
        console.log("Failed to load local xtalk-client, falling back to CDN:", e)
        return await import("https://unpkg.com/xtalk-client@latest/dist/index.js");
    }
}

const { createSession } = await loadXtalk();

function getWebSocketURL() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const wsPath = new URL("./ws", window.location.href);
    wsPath.protocol = proto;
    wsPath.host = window.location.host;
    return wsPath;
}

const session = createSession(getWebSocketURL());

const $btnStart = document.getElementById('btn-start');
const $btnStop = document.getElementById('btn-stop');
const $btnMute = document.getElementById('btn-mute');
const $voiceSelect = document.getElementById('voice-select');
const $btnUploadFile = document.getElementById('btn-upload-file');
const $fileInput = document.getElementById('file-input');
const $streamState = document.getElementById('stream-state');
const $sessionId = document.getElementById('session-id');
const $waveform = document.getElementById('waveform');
const $messages = document.getElementById('messages');

let audioCtx = null;
let inputAnalyser = null;
let outputAnalyser = null;
let inputDataArray = null;
let outputDataArray = null;
let inputBufferLength = 0;
let outputBufferLength = 0;
let rafId = null;
let isActive = false;
let currentStreamState = 'idle';

const canvasCtx = $waveform.getContext('2d');

const STATE_COLORS = {
    idle: '#6b7280',
    listening: '#34d399',
    processing: '#fbbf24',
    speaking: '#93c5fd'
};

function ensureAudioContext() {
    if (!audioCtx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        audioCtx = new AC();
    }
    return audioCtx;
}

function resizeCanvas() {
    const dpr = window.devicePixelRatio || 1;
    const { clientWidth, clientHeight } = $waveform;
    const width = Math.max(1, Math.floor(clientWidth * dpr));
    const height = Math.max(1, Math.floor(clientHeight * dpr));
    if ($waveform.width !== width || $waveform.height !== height) {
        $waveform.width = width;
        $waveform.height = height;
    }
}

function drawWaveform() {
    if (!isActive) return;
    rafId = requestAnimationFrame(drawWaveform);

    const w = $waveform.width;
    const h = $waveform.height;

    canvasCtx.fillStyle = '#0f172a';
    canvasCtx.fillRect(0, 0, w, h);

    canvasCtx.strokeStyle = '#1f2937';
    canvasCtx.lineWidth = 1;
    canvasCtx.beginPath();
    canvasCtx.moveTo(0, h / 2);
    canvasCtx.lineTo(w, h / 2);
    canvasCtx.stroke();

    const color = STATE_COLORS[currentStreamState] || '#6b7280';
    let dataArray = null;
    let bufferLength = 0;

    if (currentStreamState === 'speaking' && outputAnalyser && outputDataArray) {
        outputAnalyser.getByteTimeDomainData(outputDataArray);
        dataArray = outputDataArray;
        bufferLength = outputBufferLength;
    } else if (inputAnalyser && inputDataArray) {
        inputAnalyser.getByteTimeDomainData(inputDataArray);
        dataArray = inputDataArray;
        bufferLength = inputBufferLength;
    }

    if (dataArray && bufferLength) {
        const sliceWidth = w / bufferLength;
        canvasCtx.strokeStyle = color;
        canvasCtx.lineWidth = 2;
        canvasCtx.beginPath();
        let x = 0;
        for (let i = 0; i < bufferLength; i++) {
            const v = dataArray[i] / 128.0;
            const y = (v * h) / 2;
            if (i === 0) canvasCtx.moveTo(x, y);
            else canvasCtx.lineTo(x, y);
            x += sliceWidth;
        }
        canvasCtx.lineTo(w, h / 2);
        canvasCtx.stroke();
    }
}

function startVisualization() {
    if (isActive) return;
    ensureAudioContext();
    resizeCanvas();
    isActive = true;
    drawWaveform();
}

function stopVisualization() {
    if (!isActive) return;
    isActive = false;
    if (rafId) {
        cancelAnimationFrame(rafId);
        rafId = null;
    }
    const w = $waveform.width;
    const h = $waveform.height;
    canvasCtx.fillStyle = '#0f172a';
    canvasCtx.fillRect(0, 0, w, h);
}

session.onStateChange((state) => {
    $streamState.textContent = state.streamState;
    $sessionId.textContent = state.currentSessionId || '--';
    currentStreamState = state.streamState;

    $messages.innerHTML = '';
    for (const msg of state.messages) {
        const el = document.createElement('div');
        el.className = 'message message-' + msg.role;
        el.textContent = msg.content;
        $messages.appendChild(el);
    }
    $messages.scrollTop = $messages.scrollHeight;
});

session.onInputAudioChunk((pcmChunkInt16, sampleRate) => {
    try {
        ensureAudioContext();
        if (!inputAnalyser) {
            inputAnalyser = audioCtx.createAnalyser();
            inputAnalyser.fftSize = 1024;
            inputAnalyser.smoothingTimeConstant = 0.7;
            inputBufferLength = inputAnalyser.fftSize;
            inputDataArray = new Uint8Array(inputBufferLength);
        }

        const int16 = new Int16Array(pcmChunkInt16);
        const float32 = new Float32Array(int16.length);
        for (let i = 0; i < int16.length; i++) {
            float32[i] = int16[i] / 32768;
        }

        const buffer = audioCtx.createBuffer(1, float32.length, sampleRate);
        buffer.getChannelData(0).set(float32);
        const source = audioCtx.createBufferSource();
        source.buffer = buffer;
        source.connect(inputAnalyser);
        const gain = audioCtx.createGain();
        gain.gain.value = 0;
        inputAnalyser.connect(gain);
        gain.connect(audioCtx.destination);
        source.start();
        source.addEventListener('ended', () => {
            try { source.disconnect(); } catch { }
        });
    } catch (e) {
        console.error('Input audio chunk error:', e);
    }
});

session.onOutputAudioChunk((pcmChunkInt16, sampleRate) => {
    try {
        ensureAudioContext();
        if (!outputAnalyser) {
            outputAnalyser = audioCtx.createAnalyser();
            outputAnalyser.fftSize = 1024;
            outputAnalyser.smoothingTimeConstant = 0.7;
            outputBufferLength = outputAnalyser.fftSize;
            outputDataArray = new Uint8Array(outputBufferLength);
        }

        const int16 = new Int16Array(pcmChunkInt16);
        const float32 = new Float32Array(int16.length);
        for (let i = 0; i < int16.length; i++) {
            float32[i] = int16[i] / 32768;
        }

        const buffer = audioCtx.createBuffer(1, float32.length, sampleRate);
        buffer.getChannelData(0).set(float32);
        const source = audioCtx.createBufferSource();
        source.buffer = buffer;
        source.connect(outputAnalyser);
        const gain = audioCtx.createGain();
        gain.gain.value = 0;
        outputAnalyser.connect(gain);
        gain.connect(audioCtx.destination);
        source.start();
        source.addEventListener('ended', () => {
            try { source.disconnect(); } catch { }
        });
    } catch (e) {
        console.error('Output audio chunk error:', e);
    }
});

$btnStart.addEventListener('click', async () => {
    try {
        await session.open();
        startVisualization();
        $btnStart.disabled = true;
        $btnStop.disabled = false;
    } catch (e) {
        alert('Failed to start: ' + (e?.message || e));
    }
});

$btnStop.addEventListener('click', async () => {
    try {
        await session.close();
        stopVisualization();
        $btnStart.disabled = false;
        $btnStop.disabled = true;
    } catch (e) {
        alert('Failed to stop: ' + (e?.message || e));
    }
});

$btnMute.addEventListener('click', () => {
    try {
        session.muted = !session.muted;
        $btnMute.textContent = session.muted ? 'Unmute' : 'Mute';
    } catch (e) {
        alert('Failed to toggle mute: ' + (e?.message || e));
    }
});

window.addEventListener('resize', () => {
    resizeCanvas();
});

$btnStop.disabled = true;

let availableAudios = [];

function syncVoiceSelectValue(targetName) {
    if (!$voiceSelect) return;
    const desired = targetName || session.state.currentVoiceName || '';
    if (!desired) return;
    if ($voiceSelect.value === desired) return;
    const hasOption = Array.from($voiceSelect.options).some(opt => opt.value === desired);
    if (hasOption) {
        $voiceSelect.value = desired;
    }
}

async function loadReferenceAudios() {
    try {
        const response = await fetch('./api/voices');
        const data = await response.json();
        availableAudios = data.audios || [];

        $voiceSelect.innerHTML = '<option value="" selected disabled hidden></option>';
        availableAudios.forEach((audio, index) => {
            const voiceName = audio.name || audio.path || `voice_${index}`;
            const option = document.createElement('option');
            option.value = voiceName;
            option.textContent = voiceName;
            option.dataset.path = audio.path || '';
            $voiceSelect.appendChild(option);
        });

        $voiceSelect.disabled = false;
    } catch (error) {
        console.error('Failed to load reference audios:', error);
        $voiceSelect.innerHTML = '<option value="">Load failed</option>';
    }
}

$voiceSelect.addEventListener('change', (e) => {
    const selectedName = e.target.value;
    const selectedAudio = availableAudios.find(a => (a.name || a.path) === selectedName);
    if (selectedAudio) {
        const voiceName = selectedAudio.name || selectedName;
        session.changeVoice(voiceName);
        session.state.currentVoiceName = voiceName;
        session.state.currentVoicePath = selectedAudio.path || null;
        syncVoiceSelectValue(voiceName);
    }
});

$btnUploadFile.addEventListener('click', () => {
    $fileInput.click();
});

$fileInput.addEventListener('change', async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
        await session.uploadFile(file);
    } catch (err) {
        alert('Failed to upload file: ' + (err?.message || err));
    }
    $fileInput.value = '';
});

loadReferenceAudios();
