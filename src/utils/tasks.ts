// ─── API Types (matching OpenAPI spec) ────────────────────────────────────────

export type ExecutionMode = 'prompt' | 'script'
export type TaskStatus = 'enabled' | 'disabled' | 'running'
export type RunStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled'
export type RunTrigger = 'cron' | 'manual' | 'agent' | 'telegram'
export type LastRunStatus = 'success' | 'failed' | 'cancelled'
export type LogType = 'script_start' | 'script_stdout' | 'script_stderr' | 'script_end' | 'tool_call'

export interface EnvVarRef {
    key: string
    secret_ref: string
}

export interface Task {
    id: string
    name: string
    description?: string
    execution_mode: ExecutionMode
    payload: string
    cron_expression: string | null
    status: TaskStatus
    last_run_at?: string | null
    last_run_status?: LastRunStatus | null
    last_run_trigger?: RunTrigger | null
    created_at: string
    updated_at: string
    env_var_refs: EnvVarRef[]
}

export interface Run {
    id: string
    task_id: string
    trigger: RunTrigger
    override_prompt?: string | null
    status: RunStatus
    started_at: string
    finished_at: string | null
    error_message: string | null
}

export interface LogEntry {
    id: string
    run_id: string
    step_index: number
    log_type: LogType
    tool_name?: string | null
    input_params?: Record<string, any> | null
    output?: Record<string, any> | null
    content?: string | null
    metadata: {
        python_version?: string
        platform?: string
        injected_env_keys?: string[]
        chunk_index?: number
        exit_code?: number
        retry_count?: number
    }
    status: 'success' | 'failed'
    duration_ms: number
    timestamp: string
}

export interface TaskCreateForm {
    name: string
    description: string
    execution_mode: ExecutionMode
    payload: string
    cron_expression: string | null
    env_var_refs: EnvVarRef[]
}

export interface TaskUpdateForm {
    name?: string
    description?: string
    execution_mode?: ExecutionMode
    payload?: string
    cron_expression?: string | null
    env_var_refs?: EnvVarRef[]
}

// ─── Display Helpers ──────────────────────────────────────────────────────────

export const TASK_STATUS_COLOR: Record<TaskStatus, string> = {
    enabled: 'success',
    disabled: 'grey',
    running: 'primary',
}

export const TASK_STATUS_ICON: Record<TaskStatus, string> = {
    enabled: 'mdi-check-circle',
    disabled: 'mdi-pause-circle',
    running: 'mdi-play-circle',
}

export const RUN_STATUS_COLOR: Record<RunStatus, string> = {
    pending: 'grey',
    running: 'primary',
    success: 'success',
    failed: 'error',
    cancelled: 'warning',
}

export const RUN_STATUS_ICON: Record<RunStatus, string> = {
    pending: 'mdi-circle-outline',
    running: 'mdi-circle-slice-4',
    success: 'mdi-check-circle',
    failed: 'mdi-close-circle',
    cancelled: 'mdi-cancel',
}

export const TRIGGER_ICON: Record<RunTrigger, string> = {
    cron: 'mdi-clock-outline',
    manual: 'mdi-hand-pointing-right',
    agent: 'mdi-robot-outline',
    telegram: 'mdi-send',
}

export const TRIGGER_LABEL: Record<RunTrigger, string> = {
    cron: '定时',
    manual: '手动',
    agent: '智能体',
    telegram: 'Telegram',
}

export const MODE_ICON: Record<ExecutionMode, string> = {
    prompt: 'mdi-chat-outline',
    script: 'mdi-code-tags',
}

export const MODE_LABEL: Record<ExecutionMode, string> = {
    prompt: '提示词',
    script: '脚本',
}

export const TASK_STATUS_LABEL: Record<TaskStatus, string> = {
    enabled: '启用中',
    disabled: '已禁用',
    running: '运行中',
}

export const RUN_STATUS_LABEL: Record<RunStatus, string> = {
    pending: '等待中',
    running: '运行中',
    success: '成功',
    failed: '失败',
    cancelled: '已取消',
}

export function formatDuration (ms?: number | null): string {
    if (ms == null) return '—'
    if (ms < 1000) return `${ms}ms`
    if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
    return `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`
}

export function formatDateTime (iso?: string | null): string {
    if (!iso) return '—'
    try {
        // Handle numeric string timestamps (seconds or milliseconds)
        const num = Number(iso)
        if (!isNaN(num) && num > 0) {
            const ms = num < 1e12 ? num * 1000 : num
            return new Date(ms).toLocaleString('zh-CN', { hour12: false })
        }
        const d = new Date(iso)
        if (isNaN(d.getTime())) return iso
        return d.toLocaleString('zh-CN', { hour12: false })
    } catch {
        return iso
    }
}

export function cronToHuman (cron: string | null): string {
    if (!cron) return '仅手动执行'
    const parts = cron.trim().split(/\s+/)
    if (parts.length !== 5) return cron

    const [min, hour, dom, mon, dow] = parts

    if (min === '*' && hour === '*') return '每分钟'
    if (min!.startsWith('*/')) return `每 ${min!.slice(2)} 分钟`
    if (hour === '*') return `每小时 :${min!.padStart(2, '0')}`
    if (dom === '*' && mon === '*' && dow === '*') return `每天 ${hour!.padStart(2, '0')}:${min!.padStart(2, '0')}`
    if (dom === '*' && mon === '*' && dow === '1-5') return `工作日 ${hour!.padStart(2, '0')}:${min!.padStart(2, '0')}`
    return cron
}
