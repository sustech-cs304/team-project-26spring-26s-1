import { computed, reactive, watch } from 'vue'

export const ONBOARDING_VERSION = '2026-04-home-onboarding-v1'

const STORAGE_KEYS = {
    onboardingState: 'opencrab.onboarding.state',
    userProfile: 'opencrab.onboarding.userProfile',
    campusAuth: 'opencrab.onboarding.campusAuth',
    modelEndpoint: 'opencrab.onboarding.modelEndpoint',
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

export interface ModelEndpointConfig {
    provider: 'OpenAI' | 'DeepSeek' | 'Local Ollama'
    baseUrl: string
    apiKey: string
    modelName: string
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
    baseUrl: 'https://api.openai.com/v1',
    apiKey: '',
    modelName: '',
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
        return { ...fallback, ...JSON.parse(raw) } as T
    } catch {
        return fallback
    }
}

function writeStorage<T> (key: string, value: T): void {
    if (!isClient()) return
    window.localStorage.setItem(key, JSON.stringify(value))
}

const onboardingState = reactive<OnboardingState>(readStorage(STORAGE_KEYS.onboardingState, defaultOnboardingState()))
const userProfile = reactive<UserProfileConfig>(readStorage(STORAGE_KEYS.userProfile, defaultUserProfile()))
const campusAuth = reactive<CampusAuthConfig>(readStorage(STORAGE_KEYS.campusAuth, defaultCampusAuth()))
const modelEndpoint = reactive<ModelEndpointConfig>(readStorage(STORAGE_KEYS.modelEndpoint, defaultModelEndpoint()))
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

watch(campusAuth, (value) => {
    writeStorage(STORAGE_KEYS.campusAuth, value)
}, { deep: true })

watch(modelEndpoint, (value) => {
    writeStorage(STORAGE_KEYS.modelEndpoint, value)
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

    function saveModelEndpoint (payload: Partial<ModelEndpointConfig>): void {
        Object.assign(modelEndpoint, payload)
    }

    function saveKnowledgePack (payload: Partial<KnowledgePackConfig>): void {
        Object.assign(knowledgePack, payload)
    }

    return {
        onboardingState,
        onboardingCompleted,
        userProfile,
        campusAuth,
        modelEndpoint,
        knowledgePack,
        saveUserProfile,
        saveCampusAuth,
        saveModelEndpoint,
        saveKnowledgePack,
        markOnboardingCompleted,
        resetOnboardingCompletion,
    }
}
