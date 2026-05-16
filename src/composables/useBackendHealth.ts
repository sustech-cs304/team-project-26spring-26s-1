import { checkBackendHealth } from '@/api/health'
import { computed, readonly, ref } from 'vue'

type BackendHealthStatus = 'checking' | 'online' | 'offline'

const POLL_INTERVAL_MS = 3000
const DISCONNECT_TIMEOUT_MS = 15000
const TIP_INTERVAL_MS = 2600

const tips = [
    '小蟹正在醒来，先伸个懒腰。',
    'OpenCrab 正在整理自己的书包，马上回来。',
    '小蟹还在找今天要用的工具，请稍等一下。',
    'OpenCrab 正在把自己的钳子校准到最佳状态。',
    '小蟹听见你了，正在从壳里探头。',
    '别急，OpenCrab 正在确认自己已经准备好陪你工作。',
]

const status = ref<BackendHealthStatus>('checking')
const disconnectedSince = ref(Date.now())
const now = ref(Date.now())
const tipIndex = ref(0)
const isCheckingNow = ref(false)

let pollTimer: ReturnType<typeof window.setInterval> | null = null
let clockTimer: ReturnType<typeof window.setInterval> | null = null
let tipTimer: ReturnType<typeof window.setInterval> | null = null
let inFlight = false

const isConnected = computed(() => status.value === 'online')
const isBlocking = computed(() => !isConnected.value)
const disconnectedElapsedMs = computed(() => isBlocking.value ? now.value - disconnectedSince.value : 0)
const hasTimedOut = computed(() => disconnectedElapsedMs.value >= DISCONNECT_TIMEOUT_MS)

const title = computed(() => {
    if (hasTimedOut.value) return 'OpenCrab 还没准备好'
    if (status.value === 'offline') return 'OpenCrab 暂时走神了'
    return 'OpenCrab 正在醒来'
})

const message = computed(() => {
    if (hasTimedOut.value) {
        return '可以重新启动 OpenCrab，或稍后让小蟹再检查一次。'
    }

    return tips[tipIndex.value]
})

function markDisconnected () {
    if (status.value === 'online') {
        disconnectedSince.value = Date.now()
        tipIndex.value = 0
    }

    status.value = 'offline'
    now.value = Date.now()
}

async function runHealthCheck () {
    if (inFlight) return

    inFlight = true
    isCheckingNow.value = true

    try {
        const healthy = await checkBackendHealth()

        if (healthy) {
            status.value = 'online'
            tipIndex.value = 0
        } else {
            markDisconnected()
        }
    } catch {
        markDisconnected()
    } finally {
        inFlight = false
        isCheckingNow.value = false
        now.value = Date.now()
    }
}

function startBackendHealthPolling () {
    if (!clockTimer) {
        clockTimer = window.setInterval(() => {
            now.value = Date.now()
        }, 1000)
    }

    if (!tipTimer) {
        tipTimer = window.setInterval(() => {
            if (!isBlocking.value || hasTimedOut.value) return
            tipIndex.value = (tipIndex.value + 1) % tips.length
        }, TIP_INTERVAL_MS)
    }

    if (!pollTimer) {
        void runHealthCheck()
        pollTimer = window.setInterval(() => {
            void runHealthCheck()
        }, POLL_INTERVAL_MS)
    }
}

function retryBackendHealthCheck () {
    disconnectedSince.value = Date.now()
    now.value = Date.now()
    tipIndex.value = 0
    status.value = 'checking'
    void runHealthCheck()
}

export function useBackendHealth () {
    return {
        status: readonly(status),
        title,
        message,
        isBlocking,
        isCheckingNow: readonly(isCheckingNow),
        hasTimedOut,
        startBackendHealthPolling,
        retryBackendHealthCheck,
    }
}
