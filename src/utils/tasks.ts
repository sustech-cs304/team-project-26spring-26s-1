// ─── Task Types ────────────────────────────────────────────────────────────────
export type TaskStatus = 'running' | 'paused' | 'pending' | 'failed' | 'completed'
export type TaskType = 'recurring' | 'scheduled' | 'event-triggered' | 'monitor'

// ─── SOP Step Types ────────────────────────────────────────────────────────────
export type TaskStepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
export type RunStatus = 'success' | 'failed' | 'partial' | 'running'

export interface TaskStep {
    id: string
    index: number
    name: string
    description?: string
    status: TaskStepStatus
    duration?: number
    startedAt?: string
    completedAt?: string
    input?: string
    output?: string
    errorMessage?: string
    toolName?: string
}

export interface TaskRunLog {
    id: string
    runNumber: number
    status: RunStatus
    startedAt: string
    completedAt?: string
    duration?: number
    stepsCompleted: number
    stepsTotal: number
    triggerType: 'scheduled' | 'manual' | 'event'
    summary?: string
    errorMessage?: string
    steps: TaskStep[]
}

export interface Task {
    id: number
    name: string
    description?: string
    type: TaskType
    status: TaskStatus
    intervalLabel?: string
    scheduledAt?: string
    eventSource?: string
    triggerCondition?: string
    monitorTarget?: string
    lastRunAt?: string
    nextRunAt?: string
    runCount?: number
    failCount?: number
    tags?: string[]
    createdAt?: string
    logs?: TaskLog[]
    // SOP fields
    steps: TaskStep[]
    runLogs: TaskRunLog[]
    currentRun?: TaskRunLog
    lastRunDuration?: number
    successRate?: number
    averageDuration?: number
}

export interface TaskLog {
    time: string
    level: 'info' | 'warn' | 'error'
    message: string
}

export interface TaskForm {
    type: TaskType
    name: string
    description: string
    cron: string
    intervalLabel: string
    scheduledAt: string
    eventSource: string
    triggerCondition: string
    monitorTarget: string
    pollInterval: string
    tags: string[]
}

// ─── Task Helpers ──────────────────────────────────────────────────────────────
export const TASK_TYPE_ICON: Record<TaskType, string> = {
    recurring: 'mdi-refresh',
    scheduled: 'mdi-clock-outline',
    'event-triggered': 'mdi-lightning-bolt',
    monitor: 'mdi-eye-outline',
}

export const TASK_TYPE_COLOR: Record<TaskType, string> = {
    recurring: 'primary',
    scheduled: 'info',
    'event-triggered': 'warning',
    monitor: 'success',
}

export const TASK_STATUS_COLOR: Record<TaskStatus, string | undefined> = {
    running: 'success',
    paused: 'warning',
    pending: 'info',
    failed: 'error',
    completed: undefined,
}

export const TASK_STATUS_COLOR_RAW: Record<TaskStatus, string> = {
    paused: 'rgb(var(--v-theme-warning))',
    pending: 'rgb(var(--v-theme-info))',
    failed: 'rgb(var(--v-theme-error))',
    completed: '#888',
    running: '',
}

export const typeIcon = (type: TaskType) => TASK_TYPE_ICON[type]
export const typeIconColor = (type: TaskType) => TASK_TYPE_COLOR[type]
export const statusColor = (s: TaskStatus) => TASK_STATUS_COLOR[s]
export const statusColorRaw = (s: TaskStatus) => TASK_STATUS_COLOR_RAW[s] ?? ''

export const makeEmptyForm = (): TaskForm => ({
    type: 'recurring',
    name: '',
    description: '',
    cron: '',
    intervalLabel: '',
    scheduledAt: '',
    eventSource: '',
    triggerCondition: '',
    monitorTarget: '',
    pollInterval: '5 min',
    tags: [],
})

// ─── Step Helpers ──────────────────────────────────────────────────────────────
export const STEP_STATUS_COLOR: Record<TaskStepStatus, string> = {
    completed: 'success',
    running: 'primary',
    pending: 'grey',
    failed: 'error',
    skipped: 'grey-lighten-1',
}

export const STEP_STATUS_ICON: Record<TaskStepStatus, string> = {
    completed: 'mdi-check-circle',
    running: 'mdi-circle-slice-4',
    pending: 'mdi-circle-outline',
    failed: 'mdi-close-circle',
    skipped: 'mdi-minus-circle-outline',
}

export const RUN_STATUS_COLOR: Record<RunStatus, string> = {
    success: 'success',
    failed: 'error',
    partial: 'warning',
    running: 'primary',
}

export const RUN_STATUS_ICON: Record<RunStatus, string> = {
    success: 'mdi-check-circle',
    failed: 'mdi-close-circle',
    partial: 'mdi-alert-circle',
    running: 'mdi-circle-slice-4',
}

export function formatDuration (ms?: number): string {
    if (!ms) return '—'
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(1)}s`
}

export function makeEmptyTask (): Omit<Task, 'id'> {
    return {
        name: '', type: 'recurring', status: 'pending',
        steps: [], runLogs: [], runCount: 0,
        createdAt: new Date().toISOString().slice(0, 10),
    }
}

export const taskToForm = (task: Task): TaskForm => ({
    type: task.type,
    name: task.name,
    description: task.description ?? '',
    cron: '',
    intervalLabel: task.intervalLabel ?? '',
    scheduledAt: task.scheduledAt ?? '',
    eventSource: task.eventSource ?? '',
    triggerCondition: task.triggerCondition ?? '',
    monitorTarget: task.monitorTarget ?? '',
    pollInterval: '5 min',
    tags: [...(task.tags ?? [])],
})

export const formToTaskPatch = (form: TaskForm): Partial<Task> => ({
    name: form.name,
    description: form.description,
    type: form.type,
    intervalLabel: form.intervalLabel,
    scheduledAt: form.scheduledAt,
    eventSource: form.eventSource,
    triggerCondition: form.triggerCondition,
    monitorTarget: form.monitorTarget,
    tags: form.tags,
})
