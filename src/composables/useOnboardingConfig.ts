import { computed, reactive, watch } from 'vue'

export const ONBOARDING_VERSION = '2026-05-service-config-v1'

const STORAGE_KEYS = {
    onboardingState: 'opencrab.onboarding.state',
    userProfile: 'opencrab.onboarding.userProfile',
    campusAuth: 'opencrab.onboarding.campusAuth',
    serviceConfig: 'opencrab.onboarding.serviceConfig',
    knowledgePack: 'opencrab.onboarding.knowledgePack',
} as const

export interface OnboardingState {
    version: string
    completed: boolean
    completedAt: string | null
}

export interface UserProfileConfig {
    oneLineProfile: string
    identity: 'student'
    school: 'SUSTech'
    major: 'cs'
    ageBand: 'undergraduate' | 'graduate'
}

export interface CampusAuthConfig {
    enabled: boolean
    studentId: string
    password: string
}

export type ModelProviderType = 'OpenAI' | 'Qwen' | 'Anthropic'

export interface ModelEndpointConfig {
    provider: ModelProviderType
    baseUrl: string
    apiKey: string
    model: string
    maxTokenCount: number
}

export interface EmbedEndpointConfig {
    baseUrl: string
    apiKey: string
    model: string
    dims: number
}

export interface RerankEndpointConfig {
    baseUrl: string
    apiKey: string
    model: string
}

export interface AsrEndpointConfig {
    baseUrl: string
    apiKey: string
}

export interface MineruConfig {
    baseUrl: string
    apiKey: string
}

export interface ServiceConfig {
    agent: ModelEndpointConfig
    utility: ModelEndpointConfig
    embed: EmbedEndpointConfig
    rerank: RerankEndpointConfig
    asr: AsrEndpointConfig
    mineru: MineruConfig
}

export interface KnowledgePackConfig {
    packId: 'sustech-cs'
    status: 'idle' | 'downloading' | 'ready' | 'failed'
    lastTriggeredAt: string | null
}

const defaultOnboardingState = (): OnboardingState => ({
    version: ONBOARDING_VERSION,
    completed: false,
    completedAt: null,
})

const defaultUserProfile = (): UserProfileConfig => ({
    oneLineProfile: '',
    identity: 'student',
    school: 'SUSTech',
    major: 'cs',
    ageBand: 'undergraduate',
})

const defaultCampusAuth = (): CampusAuthConfig => ({
    enabled: false,
    studentId: '',
    password: '',
})

const defaultModelEndpoint = (): ModelEndpointConfig => ({
    provider: 'OpenAI',
    baseUrl: '',
    apiKey: '',
    model: '',
    maxTokenCount: 128000,
})

const defaultServiceConfig = (): ServiceConfig => ({
    agent: defaultModelEndpoint(),
    utility: defaultModelEndpoint(),
    embed: {
        baseUrl: 'https://api.siliconflow.cn/v1',
        apiKey: '',
        model: 'BAAI/bge-m3',
        dims: 1536,
    },
    rerank: {
        baseUrl: 'https://api.siliconflow.cn/v1',
        apiKey: '',
        model: 'BAAI/bge-reranker-v2-m3',
    },
    asr: {
        baseUrl: 'wss://dashscope.aliyuncs.com/api-ws/v1/inference/',
        apiKey: '',
    },
    mineru: {
        baseUrl: 'https://mineru.net/api/v1/agent',
        apiKey: '',
    },
})

const defaultKnowledgePack = (): KnowledgePackConfig => ({
    packId: 'sustech-cs',
    status: 'idle',
    lastTriggeredAt: null,
})

function isClient (): boolean {
    return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function readStorage<T> (key: string, fallback: T): T {
    if (!isClient()) return fallback

    try {
        const raw = window.localStorage.getItem(key)
        if (!raw) return fallback
        return mergeWithFallback(fallback, JSON.parse(raw))
    } catch {
        return fallback
    }
}

function mergeWithFallback<T> (fallback: T, value: unknown): T {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
        return fallback
    }

    const output = { ...(fallback as Record<string, unknown>) }

    for (const [key, nextValue] of Object.entries(value)) {
        const fallbackValue = output[key]

        if (
            fallbackValue
            && typeof fallbackValue === 'object'
            && !Array.isArray(fallbackValue)
            && nextValue
            && typeof nextValue === 'object'
            && !Array.isArray(nextValue)
        ) {
            output[key] = mergeWithFallback(fallbackValue, nextValue)
        } else {
            output[key] = nextValue
        }
    }

    return output as T
}

function writeStorage<T> (key: string, value: T): void {
    if (!isClient()) return
    window.localStorage.setItem(key, JSON.stringify(value))
}

const onboardingState = reactive<OnboardingState>(readStorage(STORAGE_KEYS.onboardingState, defaultOnboardingState()))
const userProfile = reactive<UserProfileConfig>(readStorage(STORAGE_KEYS.userProfile, defaultUserProfile()))
const campusAuth = reactive<CampusAuthConfig>(defaultCampusAuth())
const serviceConfig = reactive<ServiceConfig>(defaultServiceConfig())
const knowledgePack = reactive<KnowledgePackConfig>(readStorage(STORAGE_KEYS.knowledgePack, defaultKnowledgePack()))

if (knowledgePack.status === 'downloading') {
    knowledgePack.status = 'idle'
}

watch(onboardingState, (value) => {
    writeStorage(STORAGE_KEYS.onboardingState, value)
}, { deep: true })

watch(userProfile, (value) => {
    writeStorage(STORAGE_KEYS.userProfile, value)
}, { deep: true })

watch(knowledgePack, (value) => {
    writeStorage(STORAGE_KEYS.knowledgePack, value)
}, { deep: true })

export function getOnboardingStateSnapshot (): OnboardingState {
    const saved = readStorage(STORAGE_KEYS.onboardingState, defaultOnboardingState())
    if (saved.version !== ONBOARDING_VERSION) return defaultOnboardingState()
    return saved
}

export function isOnboardingCompleted (): boolean {
    const state = getOnboardingStateSnapshot()
    return state.version === ONBOARDING_VERSION && state.completed
}

export function useOnboardingConfig () {
    const onboardingCompleted = computed(() =>
        onboardingState.version === ONBOARDING_VERSION && onboardingState.completed
    )

    function markOnboardingCompleted (): void {
        onboardingState.version = ONBOARDING_VERSION
        onboardingState.completed = true
        onboardingState.completedAt = new Date().toISOString()
    }

    function resetOnboardingCompletion (): void {
        onboardingState.version = ONBOARDING_VERSION
        onboardingState.completed = false
        onboardingState.completedAt = null
    }

    function saveUserProfile (payload: Partial<UserProfileConfig>): void {
        Object.assign(userProfile, payload)
    }

    function saveCampusAuth (payload: Partial<CampusAuthConfig>): void {
        Object.assign(campusAuth, payload)
    }

    function saveServiceConfig (payload: Partial<ServiceConfig>): void {
        Object.assign(serviceConfig, payload)
    }

    function saveKnowledgePack (payload: Partial<KnowledgePackConfig>): void {
        Object.assign(knowledgePack, payload)
    }

    return {
        onboardingState,
        onboardingCompleted,
        userProfile,
        campusAuth,
        serviceConfig,
        knowledgePack,
        saveUserProfile,
        saveCampusAuth,
        saveServiceConfig,
        saveKnowledgePack,
        markOnboardingCompleted,
        resetOnboardingCompletion,
    }
}
