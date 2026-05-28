import { checkBackendHealth } from '@/api/health'
import { computed, readonly, ref } from 'vue'

type BackendHealthStatus = 'checking' | 'online' | 'offline'

const POLL_INTERVAL_MS = 3000
const DISCONNECT_TIMEOUT_MS = 60000
const TIP_INTERVAL_MS = 2600
const shouldSkipBackendHealthCheck = import.meta.env.MODE === 'tauri-dev'
    || import.meta.env.VITE_SKIP_BACKEND_HEALTH_CHECK === 'true'

const tips = [
    'OpenCrab 正在启动，第一次见面可能会多花几秒。',
    '小蟹正在打开工具箱，准备好后会自动带你进去。',
    'OpenCrab 正在接通自己的工作区，请稍等一下。',
    '小蟹还在热身，马上就能开始干活。',
    'OpenCrab 正在整理今天要用的能力，很快就绪。',
    '小蟹正在确认一切准备妥当，马上回来。',
]

const status = ref<BackendHealthStatus>(shouldSkipBackendHealthCheck ? 'online' : 'checking')
const disconnectedSince = ref(Date.now())
const now = ref(Date.now())
const tipIndex = ref(0)
const isCheckingNow = ref(false)
const hasConnectedOnce = ref(shouldSkipBackendHealthCheck)

let pollTimer: ReturnType<typeof window.setInterval> | null = null
let clockTimer: ReturnType<typeof window.setInterval> | null = null
let tipTimer: ReturnType<typeof window.setInterval> | null = null
let inFlight = false
let browserEventsStarted = false

const isConnected = computed(() => status.value === 'online')
const isBlocking = computed(() => !isConnected.value)
const disconnectedElapsedMs = computed(() => isBlocking.value ? now.value - disconnectedSince.value : 0)
const hasTimedOut = computed(() => disconnectedElapsedMs.value >= DISCONNECT_TIMEOUT_MS)

const title = computed(() => {
    if (hasTimedOut.value) {
        return hasConnectedOnce.value ? 'OpenCrab 暂时没跟上' : 'OpenCrab 启动还没完成'
    }
    if (status.value === 'offline') {
        return hasConnectedOnce.value ? 'OpenCrab 正在重新接上' : 'OpenCrab 正在准备中'
    }
    return 'OpenCrab 正在启动'
})

const message = computed(() => {
    if (hasTimedOut.value) {
        if (hasConnectedOnce.value) {
            return '小蟹和工作区的连接断开了一会儿。可以重新打开 OpenCrab，或让小蟹再检查一次。'
        }
        return '启动时间比平时久。可以重新打开 OpenCrab，或让小蟹再检查一次。'
    }

    if (hasConnectedOnce.value && status.value === 'offline') {
        return '小蟹刚刚没听见工作区的回应，正在帮你重新确认。'
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
            hasConnectedOnce.value = true
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
    if (shouldSkipBackendHealthCheck) {
        status.value = 'online'
        hasConnectedOnce.value = true
        return
    }

    if (!browserEventsStarted) {
        window.addEventListener('online', () => {
            void runHealthCheck()
        })
        window.addEventListener('offline', markDisconnected)
        window.addEventListener('focus', () => {
            void runHealthCheck()
        })
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                void runHealthCheck()
            }
        })
        browserEventsStarted = true
    }

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
    if (shouldSkipBackendHealthCheck) return

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
