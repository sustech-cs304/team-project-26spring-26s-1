import { ref, onUnmounted } from 'vue'

export interface AsrCallbacks {
    onTranscript?: (text: string) => void
    onError?: (message: string) => void
    onFinished?: () => void
}

export function useAsr ({ onTranscript, onError, onFinished }: AsrCallbacks = {}) {
    const isRecording = ref(false)
    const isStarting = ref(false)
    const transcript = ref('')

    let ws: WebSocket | null = null
    let audioCtx: AudioContext | null = null

    let processor: any = null
    let stream: MediaStream | null = null
    const WS_URL = 'ws://localhost:4000'

    let completedText = ''
    let currentText = ''
    let timeoutId: number | null = null
    const TIMEOUT_MS = 15000
    const START_TIMEOUT_MS = 10000

    function floatTo16BitPCM (input: Float32Array) {
        const output = new Int16Array(input.length)
        for (let i = 0; i < input.length; i++) {
            const value = input[i] ?? 0
            const s = Math.max(-1.0, Math.min(1.0, value))
            output[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
        }
        return output.buffer
    }

    function resetTimeout () {
        if (timeoutId) window.clearTimeout(timeoutId)
        timeoutId = window.setTimeout(() => {
            if (isRecording.value) {
                stopRecording()
            }
        }, TIMEOUT_MS)
    }

    function clearAsrTimeout () {
        if (timeoutId) {
            window.clearTimeout(timeoutId)
            timeoutId = null
        }
    }

    async function startRecording () {
        if (isStarting.value || isRecording.value) return

        isStarting.value = true
        let startTimeoutId: number | null = null

        try {
            startTimeoutId = window.setTimeout(() => {
                if (isStarting.value) {
                    onError?.('ASR服务启动超时，请重试')
                    stopRecording()
                }
            }, START_TIMEOUT_MS)

            ws = new WebSocket(WS_URL)

            ws.onopen = () => {
                ws?.send(JSON.stringify({ type: 'START_ASR' }))
            }

            ws.onmessage = (e) => {
                try {
                    const msg = JSON.parse(e.data)
                    if (msg.header?.event === 'task-started') {
                        if (startTimeoutId) window.clearTimeout(startTimeoutId)
                        isStarting.value = false
                        startAudioCapture()
                        isRecording.value = true
                        resetTimeout()
                    } else if (msg.header?.event === 'result-generated') {
                        const sentence = msg.payload?.output?.sentence
                        const text = sentence?.text || ''
                        const isComplete = sentence?.sentence_end === true

                        if (isComplete) {
                            completedText += (completedText ? ' ' : '') + text
                            currentText = ''
                        } else {
                            currentText = text
                        }

                        const fullText = completedText + (currentText ? ' ' + currentText : '')
                        transcript.value = fullText
                        onTranscript?.(fullText)
                        resetTimeout()
                    } else if (msg.header?.event === 'task-finished') {
                        onFinished?.()
                    }
                } catch (err) {
                    console.error('Failed to parse ASR message:', err)
                }
            }

            ws.onerror = () => {
                if (startTimeoutId) window.clearTimeout(startTimeoutId)
                isStarting.value = false
                onError?.('连接ASR服务失败，请确保服务器已启动')
                stopRecording()
            }
        } catch (err) {
            if (startTimeoutId) window.clearTimeout(startTimeoutId)
            isStarting.value = false
            onError?.('WebSocket连接失败')
            console.error('WebSocket error:', err)
        }
    }

    async function startAudioCapture () {
        try {
            audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 })
            stream = await navigator.mediaDevices.getUserMedia({ audio: true })
            const source = audioCtx.createMediaStreamSource(stream)
            processor = audioCtx.createScriptProcessor(4096, 1, 1)

            processor.onaudioprocess = (e: any) => {
                const inputData = e.inputBuffer.getChannelData(0)
                if (inputData) {
                    const pcmData = floatTo16BitPCM(inputData)
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        ws.send(pcmData)
                    }
                }
            }

            source.connect(processor)
            processor.connect(audioCtx.destination)
        } catch (err: any) {
            if (err?.name === 'NotAllowedError') {
                onError?.('未获得麦克风权限，请在浏览器设置中允许')
            } else if (err?.name === 'NotFoundError') {
                onError?.('未检测到麦克风设备')
            } else {
                onError?.(`麦克风启动失败: ${err?.message || '未知错误'}`)
            }
            stopRecording()
        }
    }

    function stopRecording () {
        isStarting.value = false
        isRecording.value = false
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'FINISH_TASK' }))
        }
        stopAudio()
        transcript.value = ''
        completedText = ''
        currentText = ''
        clearAsrTimeout()
    }

    function stopAudio () {
        clearAsrTimeout()
        if (stream) {
            stream.getTracks().forEach(track => track.stop())
            stream = null
        }
        if (processor) {
            processor.disconnect()
            processor = null
        }
        if (audioCtx) {
            audioCtx.close()
            audioCtx = null
        }
        if (ws) {
            ws.close()
            ws = null
        }
    }

    onUnmounted(() => {
        stopAudio()
    })

    return {
        isRecording,
        isStarting,
        transcript,
        startRecording,
        stopRecording,
    }
}
