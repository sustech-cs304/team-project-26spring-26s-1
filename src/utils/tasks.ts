// ─── API Types (matching OpenAPI spec) ────────────────────────────────────────

export type ExecutionMode = 'prompt' | 'script'
export type TaskStatus = 'enabled' | 'disabled' | 'running'
export type RunStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled'
export type RunTrigger = 'cron' | 'manual' | 'agent' | 'telegram'
export type LastRunStatus = 'success' | 'failed' | 'cancelled'
export type LogType = 'script_start' | 'script_stdout' | 'script_stderr' | 'script_end' | 'tool_call'

export interface EnvVarRef {
    key: string
}

export function validateEnvVarKey (key: string | null | undefined): string | null {
    const value = key ?? ''
    if (!value) return 'Name is required'
    if (value.length > 1024) return 'Name must be at most 1024 characters'
    if (/\s/.test(value)) return 'Name cannot contain spaces'
    if (!/^[A-Za-z0-9_]+$/.test(value)) {
        return 'Only letters, numbers, and underscores are allowed'
    }
    return null
}

function isValidCronNumber (value: string, min: number, max: number): boolean {
    if (!/^\d+$/.test(value)) return false
    const num = Number(value)
    return num >= min && num <= max
}

function isValidCronAtom (value: string, min: number, max: number): boolean {
    if (value === '*') return true

    if (value.includes('/')) {
        const [base, step] = value.split('/')
        if (!base || !step || !/^\d+$/.test(step) || Number(step) <= 0) return false
        return isValidCronAtom(base, min, max)
    }

    if (value.includes('-')) {
        const [start, end] = value.split('-')
        if (!start || !end) return false
        if (!isValidCronNumber(start, min, max) || !isValidCronNumber(end, min, max)) return false
        return Number(start) <= Number(end)
    }

    return isValidCronNumber(value, min, max)
}

function isValidCronField (field: string, min: number, max: number): boolean {
    return field.split(',').every(part => isValidCronAtom(part, min, max))
}

export function validateCronExpression (cron: string | null | undefined): string | null {
    const value = cron?.trim() ?? ''
    if (!value) return null

    const parts = value.split(/\s+/)
    if (parts.length !== 5) return 'Cron expression must have 5 fields'

    const ranges: Array<[number, number]> = [
        [0, 59],
        [0, 23],
        [1, 31],
        [1, 12],
        [0, 6],
    ]

    const valid = parts.every((field, index) => {
        const [min, max] = ranges[index] ?? [0, 0]
        return isValidCronField(field, min, max)
    })

    return valid ? null : 'Invalid cron format'
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
    script: 'py脚本',
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

function normalizeUtcTimestamp (value: string): string {
    const trimmed = value.trim()
    const normalized = trimmed
        .replace(' ', 'T')
        .replace(/(\.\d{3})\d+/, '$1')

    const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized)
    const isDateTime = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(normalized)

    return isDateTime && !hasTimezone ? `${normalized}Z` : normalized
}

export function parseTaskDateTime (iso?: string | null): Date | null {
    if (!iso) return null
    try {
        // Handle numeric string timestamps (seconds or milliseconds)
        const num = Number(iso)
        if (!isNaN(num) && num > 0) {
            const ms = num < 1e12 ? num * 1000 : num
            const date = new Date(ms)
            return Number.isNaN(date.getTime()) ? null : date
        }
        const date = new Date(normalizeUtcTimestamp(iso))
        return Number.isNaN(date.getTime()) ? null : date
    } catch {
        return null
    }
}

export function formatDateTime (iso?: string | null): string {
    if (!iso) return '—'
    const date = parseTaskDateTime(iso)
    if (!date) return iso
    try {
        return date.toLocaleString('zh-CN', { hour12: false })
    } catch {
        return iso
    }
}

const WEEKDAY_LABELS: Record<string, string> = {
    '0': '周日',
    '1': '周一',
    '2': '周二',
    '3': '周三',
    '4': '周四',
    '5': '周五',
    '6': '周六',
}

function padCronNumber (value: string): string {
    return value.padStart(2, '0')
}

function formatCronTime (hour: string, minute: string): string {
    return `${padCronNumber(hour)}:${padCronNumber(minute)}`
}

function cronListToHuman (value: string, labelMap?: Record<string, string>): string | null {
    if (!/^\d+(,\d+)*$/.test(value)) return null
    return value
        .split(',')
        .map(item => labelMap?.[item] ?? item)
        .join('、')
}

export function cronToHuman (cron: string | null): string {
    if (!cron) return '仅手动执行'
    const parts = cron.trim().split(/\s+/)
    if (parts.length !== 5) return cron

    const [min, hour, dom, mon, dow] = parts
    if (!min || !hour || !dom || !mon || !dow) return cron

    if (min === '*' && hour === '*') return '每分钟'

    if (min.startsWith('*/') && hour === '*' && dom === '*' && mon === '*' && dow === '*') {
        return `每 ${min.slice(2)} 分钟`
    }

    if (min === '0' && hour.startsWith('*/') && dom === '*' && mon === '*' && dow === '*') {
        return `每 ${hour.slice(2)} 小时`
    }

    if (hour === '*' && dom === '*' && mon === '*' && dow === '*') {
        return `每小时 ${padCronNumber(min)} 分`
    }

    if (/^\d+$/.test(min) && /^\d+$/.test(hour)) {
        const time = formatCronTime(hour, min)

        if (dom === '*' && mon === '*' && dow === '*') return `每天 ${time}`
        if (dom === '*' && mon === '*' && dow === '1-5') return `工作日 ${time}`

        const dowList = cronListToHuman(dow, WEEKDAY_LABELS)
        if (dom === '*' && mon === '*' && dowList) return `每周 ${dowList} ${time}`

        const domList = cronListToHuman(dom)
        if (domList && mon === '*' && dow === '*') return `每月 ${domList} 日 ${time}`

        const monList = cronListToHuman(mon)
        if (domList && monList && dow === '*') return `每年 ${monList} 月 ${domList} 日 ${time}`
    }

    return cron
}
