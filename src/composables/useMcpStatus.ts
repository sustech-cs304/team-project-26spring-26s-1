import { getMcpStatuses } from '@/api/mcp'
import { computed, readonly, ref } from 'vue'

type McpSummaryState = 'healthy' | 'enabled'

const POLL_INTERVAL_MS = 4000

const statuses = ref<Awaited<ReturnType<typeof getMcpStatuses>>>([])
const isCheckingNow = ref(false)

let pollTimer: ReturnType<typeof window.setInterval> | null = null
let browserEventsStarted = false
let inFlight = false

const enabledStatuses = computed(() =>
    statuses.value.filter(entry => entry.status !== 'disabled')
)

const aliveStatuses = computed(() =>
    enabledStatuses.value.filter(entry => entry.status === 'running')
)

const summaryState = computed<McpSummaryState>(() => {
    return aliveStatuses.value.length === enabledStatuses.value.length ? 'healthy' : 'enabled'
})

const summaryLabel = computed(() => {
    if (summaryState.value === 'healthy') return 'Healthy'
    return 'Enabled'
})

const summaryIcon = computed(() => {
    if (summaryState.value === 'healthy') return 'mdi-lan-connect'
    return 'mdi-lan-disconnect'
})

const hasEnabledServers = computed(() => enabledStatuses.value.length > 0)

async function runMcpStatusCheck () {
    if (inFlight) return

    inFlight = true
    isCheckingNow.value = true

    try {
        statuses.value = await getMcpStatuses()
    } catch {
        // Keep the previous snapshot if the status endpoint blips.
    } finally {
        inFlight = false
        isCheckingNow.value = false
    }
}

function startMcpStatusPolling () {
    if (!browserEventsStarted) {
        window.addEventListener('online', () => {
            void runMcpStatusCheck()
        })
        window.addEventListener('focus', () => {
            void runMcpStatusCheck()
        })
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                void runMcpStatusCheck()
            }
        })
        browserEventsStarted = true
    }

    if (!pollTimer) {
        void runMcpStatusCheck()
        pollTimer = window.setInterval(() => {
            void runMcpStatusCheck()
        }, POLL_INTERVAL_MS)
    }
}

function retryMcpStatusCheck () {
    void runMcpStatusCheck()
}

export function useMcpStatus () {
    return {
        statuses: readonly(statuses),
        enabledStatuses,
        aliveStatuses,
        summaryState,
        summaryLabel,
        summaryIcon,
        hasEnabledServers,
        isCheckingNow: readonly(isCheckingNow),
        startMcpStatusPolling,
        retryMcpStatusCheck,
    }
}
