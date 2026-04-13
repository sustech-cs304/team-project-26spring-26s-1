import axios from 'axios'
import http from '@/utils/http'

export type RagSyncStatus = 'idle' | 'running' | 'success' | 'failed'
export type RagSyncStage = 'idle' | 'manifest' | 'download' | 'import' | 'completed' | 'failed'

export interface RagSyncState {
    status: RagSyncStatus
    stage: RagSyncStage
    progress: number
    message: string
    knowledge_base_id: string | null
    version: string | null
    downloaded_files: string[]
    embedded_added: number
    embedded_overwritten: number
    embedded_failed: number
    error: string | null
}

export interface ApiErrorDetail {
    detail?: string
}

export const defaultRagSyncState = (): RagSyncState => ({
    status: 'idle',
    stage: 'idle',
    progress: 0,
    message: '',
    knowledge_base_id: null,
    version: null,
    downloaded_files: [],
    embedded_added: 0,
    embedded_overwritten: 0,
    embedded_failed: 0,
    error: null,
})

function normalizeSyncState(payload: Partial<RagSyncState> | null | undefined): RagSyncState {
    return {
        ...defaultRagSyncState(),
        ...payload,
        downloaded_files: Array.isArray(payload?.downloaded_files) ? payload.downloaded_files : [],
    }
}

export function triggerRagSync(): Promise<RagSyncState> {
    return http.post<RagSyncState>('/rag/sync').then(normalizeSyncState)
}

export function getRagSyncStatus(): Promise<RagSyncState> {
    return http.get<RagSyncState>('/rag/sync/status').then(normalizeSyncState)
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
    if (axios.isAxiosError<ApiErrorDetail>(error)) {
        const detail = error.response?.data?.detail
        if (typeof detail === 'string' && detail.trim()) {
            return detail.trim()
        }
    }
    return fallback
}
