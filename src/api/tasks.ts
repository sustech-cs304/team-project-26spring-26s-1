import http from '@/utils/http'
import type {
    Task, Run, LogEntry, EnvVarRef,
    TaskCreateForm, TaskUpdateForm,
} from '@/utils/tasks'

// ─── Tasks ────────────────────────────────────────────────────────────────────

interface PaginatedResponse<T> {
    total: number
    items: T[]
}

export function getTasks(params?: {
    status?: 'enabled' | 'disabled' | 'running'
    page?: number
    page_size?: number
}): Promise<PaginatedResponse<Task>> {
    return http.get<PaginatedResponse<Task>>('/tasks', { params })
}

export function getTask(taskId: string): Promise<Task> {
    return http.get<Task>(`/tasks/${taskId}`)
}

export function createTask(data: TaskCreateForm): Promise<Task> {
    return http.post<Task>('/tasks/create', data)
}

export function updateTask(taskId: string, data: TaskUpdateForm): Promise<Task> {
    return http.patch<Task>(`/tasks/${taskId}`, data)
}

export function deleteTask(taskId: string): Promise<{ message: string }> {
    return http.delete<{ message: string }>(`/tasks/${taskId}`)
}

export function enableTask(taskId: string): Promise<{ message: string }> {
    return http.post<{ message: string }>(`/tasks/${taskId}/enable`)
}

export function disableTask(taskId: string): Promise<{ message: string }> {
    return http.post<{ message: string }>(`/tasks/${taskId}/disable`)
}

export function triggerTask(taskId: string): Promise<{ run_id: string }> {
    return http.post<{ run_id: string }>(`/tasks/${taskId}/trigger`)
}

// ─── Runs ─────────────────────────────────────────────────────────────────────

export function getTaskRuns(taskId: string, params?: {
    trigger?: 'cron' | 'manual' | 'agent' | 'telegram'
    status?: 'pending' | 'running' | 'success' | 'failed' | 'cancelled'
    page?: number
    page_size?: number
}): Promise<PaginatedResponse<Run>> {
    return http.get<PaginatedResponse<Run>>(`/tasks/${taskId}/runs`, { params })
}

export function getRun(runId: string): Promise<Run> {
    return http.get<Run>(`/runs/${runId}`)
}

export function cancelRun(runId: string): Promise<Run> {
    return http.post<Run>(`/runs/${runId}/cancel`)
}

export function getRunLogs(runId: string): Promise<LogEntry[]> {
    return http.get<LogEntry[]>(`/runs/${runId}/logs`)
}

// ─── Environment Variables ────────────────────────────────────────────────────

export function getEnvVars(): Promise<EnvVarRef[]> {
    return http.get<EnvVarRef[]>('/env-vars')
}

export function upsertEnvVar(data: { key: string; value: string }): Promise<EnvVarRef> {
    return http.post<EnvVarRef>('/env-vars', data)
}

export function deleteEnvVar(key: string): Promise<{ message: string }> {
    return http.delete<{ message: string }>(`/env-vars/${key}`)
}
