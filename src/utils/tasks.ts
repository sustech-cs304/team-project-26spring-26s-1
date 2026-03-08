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

// ─── Mock Data ─────────────────────────────────────────────────────────────────
export function buildDefaultTasks (): Task[] {
    return [
        {
            id: 1, name: 'Library Seat Monitor', type: 'monitor', status: 'running',
            description: 'Monitors available seats in the library and notifies when a seat becomes available.',
            monitorTarget: 'Library Floor 3 Area A', lastRunAt: '2026-03-05 14:30',
            nextRunAt: '2026-03-05 14:35', runCount: 576, failCount: 2,
            tags: ['library', 'monitor'], createdAt: '2026-01-10',
            successRate: 99, averageDuration: 312, lastRunDuration: 320,
            steps: [
                { id: 's1-1', index: 1, name: '获取座位数据', description: '调用图书馆 API 拉取实时座位状态', status: 'completed', duration: 320, toolName: 'fetch_seat_data', startedAt: '2026-03-05 14:30:00', completedAt: '2026-03-05 14:30:00', input: '{"floor":3,"area":"A"}', output: '{"available":3,"total":50,"seats":["A3-14","A3-22","A3-31"]}' },
                { id: 's1-2', index: 2, name: '分析空闲座位', description: '分析哪些座位刚变为可用', status: 'running', toolName: 'analyze_availability', startedAt: '2026-03-05 14:30:01' },
                { id: 's1-3', index: 3, name: '发送通知', description: '通过微信或短信发送座位提醒', status: 'pending', toolName: 'send_notification' },
            ],
            runLogs: [
                { id: 'r1-576', runNumber: 576, status: 'running', startedAt: '2026-03-05 14:30', stepsCompleted: 1, stepsTotal: 3, triggerType: 'scheduled', steps: [] },
                { id: 'r1-575', runNumber: 575, status: 'success', startedAt: '2026-03-05 14:25', completedAt: '2026-03-05 14:25', duration: 285, stepsCompleted: 3, stepsTotal: 3, triggerType: 'scheduled', summary: '发现 2 个空位，通知已发送', steps: [] },
                { id: 'r1-574', runNumber: 574, status: 'success', startedAt: '2026-03-05 14:20', completedAt: '2026-03-05 14:20', duration: 310, stepsCompleted: 3, stepsTotal: 3, triggerType: 'scheduled', summary: '无新增空位', steps: [] },
                { id: 'r1-573', runNumber: 573, status: 'failed', startedAt: '2026-03-05 14:15', completedAt: '2026-03-05 14:15', duration: 150, stepsCompleted: 1, stepsTotal: 3, triggerType: 'scheduled', errorMessage: 'Library API timeout after 5s', steps: [] },
                { id: 'r1-572', runNumber: 572, status: 'success', startedAt: '2026-03-05 14:10', completedAt: '2026-03-05 14:10', duration: 298, stepsCompleted: 3, stepsTotal: 3, triggerType: 'manual', summary: '手动检测，3 个空位', steps: [] },
            ],
            logs: [
                { time: '14:30', level: 'info', message: 'Seat A3-14 became available.' },
                { time: '14:25', level: 'info', message: 'Polling library API...' },
                { time: '14:20', level: 'warn', message: 'API response slow (>2s).' },
            ],
        },
        {
            id: 2, name: 'Daily Report Generator', type: 'recurring', status: 'running',
            description: 'Generates a daily academic progress report and sends to email.',
            intervalLabel: 'Every day at 09:00', lastRunAt: '2026-03-05 09:00',
            nextRunAt: '2026-03-06 09:00', runCount: 45, failCount: 0,
            tags: ['report'], createdAt: '2026-01-15',
            successRate: 100, averageDuration: 4200, lastRunDuration: 3900,
            steps: [
                { id: 's2-1', index: 1, name: '收集学习数据', status: 'completed', duration: 1200, toolName: 'collect_study_data', output: '{"courses":5,"assignments":3,"hours":2.5}' },
                { id: 's2-2', index: 2, name: '生成报告内容', status: 'completed', duration: 2100, toolName: 'generate_report', output: '{"pages":2,"charts":3}' },
                { id: 's2-3', index: 3, name: '发送邮件', status: 'running', toolName: 'send_email', startedAt: '2026-03-05 09:00:03' },
            ],
            runLogs: [
                { id: 'r2-45', runNumber: 45, status: 'running', startedAt: '2026-03-05 09:00', stepsCompleted: 2, stepsTotal: 3, triggerType: 'scheduled', steps: [] },
                { id: 'r2-44', runNumber: 44, status: 'success', startedAt: '2026-03-04 09:00', completedAt: '2026-03-04 09:00', duration: 4100, stepsCompleted: 3, stepsTotal: 3, triggerType: 'scheduled', summary: '报告已发送至邮箱', steps: [] },
                { id: 'r2-43', runNumber: 43, status: 'success', startedAt: '2026-03-03 09:00', completedAt: '2026-03-03 09:00', duration: 4300, stepsCompleted: 3, stepsTotal: 3, triggerType: 'scheduled', summary: '报告已发送至邮箱', steps: [] },
            ],
            logs: [{ time: '09:00', level: 'info', message: 'Report sent to 19251212@mail.sustech.edu.cn.' }],
        },
        {
            id: 3, name: 'Assignment Deadline Alert', type: 'event-triggered', status: 'paused',
            description: 'Triggers an alert when a new assignment deadline is detected in Blackboard.',
            eventSource: 'Blackboard', triggerCondition: 'New assignment detected',
            lastRunAt: '2026-03-04 16:00', runCount: 12, failCount: 1,
            tags: ['alert'], createdAt: '2026-02-01',
            successRate: 92, averageDuration: 850,
            steps: [
                { id: 's3-1', index: 1, name: '监听 Blackboard 事件', status: 'completed', duration: 200, toolName: 'listen_bb_event', output: '{"event":"new_assignment","course":"CS304"}' },
                { id: 's3-2', index: 2, name: '解析截止时间', status: 'completed', duration: 150, toolName: 'parse_deadline', output: '{"deadline":"2026-03-15 23:59","daysLeft":10}' },
                { id: 's3-3', index: 3, name: '推送提醒', status: 'skipped', toolName: 'push_alert' },
            ],
            runLogs: [
                { id: 'r3-12', runNumber: 12, status: 'success', startedAt: '2026-03-04 16:00', completedAt: '2026-03-04 16:00', duration: 820, stepsCompleted: 2, stepsTotal: 3, triggerType: 'event', summary: '检测到新作业，提醒已发送', steps: [] },
                { id: 'r3-11', runNumber: 11, status: 'failed', startedAt: '2026-03-03 10:30', completedAt: '2026-03-03 10:30', duration: 300, stepsCompleted: 1, stepsTotal: 3, triggerType: 'event', errorMessage: 'Blackboard session expired', steps: [] },
            ],
        },
        {
            id: 4, name: 'Daily Study Reminder', type: 'recurring', status: 'pending',
            description: '每天定时提醒学习计划，推送今日待完成任务清单。',
            intervalLabel: 'Every day at 08:00', runCount: 0,
            tags: ['reminder', 'study'], createdAt: '2026-03-01',
            successRate: undefined, averageDuration: undefined,
            steps: [
                { id: 's4-1', index: 1, name: '读取今日任务', status: 'pending', toolName: 'fetch_tasks', description: '从任务系统获取今日待办' },
                { id: 's4-2', index: 2, name: '整理优先级', status: 'pending', toolName: 'sort_tasks', description: '按截止日期和优先级排序' },
                { id: 's4-3', index: 3, name: '生成提醒文案', status: 'pending', toolName: 'gen_message', description: '用 AI 生成个性化提醒语' },
                { id: 's4-4', index: 4, name: '发送通知', status: 'pending', toolName: 'send_push', description: '推送到微信/邮件' },
            ],
            runLogs: [
                { id: 'r4-1', runNumber: 1, status: 'success', startedAt: '2026-03-04 08:00', completedAt: '2026-03-04 08:00', duration: 2300, stepsCompleted: 4, stepsTotal: 4, triggerType: 'scheduled', summary: '今日 5 个任务已提醒', steps: [] },
                { id: 'r4-2', runNumber: 2, status: 'success', startedAt: '2026-03-03 08:00', completedAt: '2026-03-03 08:00', duration: 2100, stepsCompleted: 4, stepsTotal: 4, triggerType: 'scheduled', summary: '今日 3 个任务已提醒', steps: [] },
                { id: 'r4-3', runNumber: 3, status: 'success', startedAt: '2026-03-02 08:00', completedAt: '2026-03-02 08:00', duration: 2500, stepsCompleted: 4, stepsTotal: 4, triggerType: 'scheduled', summary: '今日 6 个任务已提醒', steps: [] },
            ],
        },
        {
            id: 5, name: 'Course Material Downloader', type: 'recurring', status: 'failed',
            description: 'Downloads new course materials from Blackboard automatically.',
            intervalLabel: 'Every hour', lastRunAt: '2026-03-05 13:00',
            runCount: 200, failCount: 5, tags: ['download'], createdAt: '2026-01-20',
            successRate: 97, averageDuration: 8500,
            steps: [
                { id: 's5-1', index: 1, name: '登录 Blackboard', status: 'failed', duration: 500, toolName: 'bb_login', errorMessage: 'Authentication failed: session expired', startedAt: '2026-03-05 13:00:00', completedAt: '2026-03-05 13:00:00' },
                { id: 's5-2', index: 2, name: '扫描新文件', status: 'pending', toolName: 'scan_files' },
                { id: 's5-3', index: 3, name: '批量下载', status: 'pending', toolName: 'batch_download' },
            ],
            runLogs: [
                { id: 'r5-200', runNumber: 200, status: 'failed', startedAt: '2026-03-05 13:00', completedAt: '2026-03-05 13:00', duration: 500, stepsCompleted: 0, stepsTotal: 3, triggerType: 'scheduled', errorMessage: 'Blackboard authentication failed (session expired)', steps: [] },
                { id: 'r5-199', runNumber: 199, status: 'success', startedAt: '2026-03-05 12:00', completedAt: '2026-03-05 12:00', duration: 7800, stepsCompleted: 3, stepsTotal: 3, triggerType: 'scheduled', summary: '下载 5 个新文件，共 48MB', steps: [] },
            ],
            logs: [{ time: '13:00', level: 'error', message: 'Blackboard authentication failed (session expired).' }],
        },
        {
            id: 6, name: 'Grade Change Watcher', type: 'monitor', status: 'running',
            description: '监控成绩系统，一旦有新成绩发布立即通知。',
            monitorTarget: 'Grade System', lastRunAt: '2026-03-05 14:00',
            nextRunAt: '2026-03-05 15:00', runCount: 88, failCount: 0,
            tags: ['grade', 'monitor'], createdAt: '2026-02-10',
            successRate: 100, averageDuration: 600,
            steps: [
                { id: 's6-1', index: 1, name: '拉取成绩快照', status: 'completed', duration: 400, toolName: 'fetch_grades', output: '{"courses":6,"updated":0}' },
                { id: 's6-2', index: 2, name: '对比历史记录', status: 'completed', duration: 50, toolName: 'diff_grades', output: '{"changed":0}' },
                { id: 's6-3', index: 3, name: '发送变更通知', status: 'skipped', toolName: 'notify_grade_change' },
            ],
            runLogs: [
                { id: 'r6-88', runNumber: 88, status: 'success', startedAt: '2026-03-05 14:00', completedAt: '2026-03-05 14:00', duration: 450, stepsCompleted: 2, stepsTotal: 3, triggerType: 'scheduled', summary: '无成绩变化', steps: [] },
                { id: 'r6-87', runNumber: 87, status: 'success', startedAt: '2026-03-05 13:00', completedAt: '2026-03-05 13:00', duration: 620, stepsCompleted: 3, stepsTotal: 3, triggerType: 'scheduled', summary: 'CS304 期中成绩发布，已通知', steps: [] },
            ],
        },
        {
            id: 7, name: 'Exam Countdown Push', type: 'scheduled', status: 'pending',
            description: '考试前 3 天、1 天、当天自动推送倒计时提醒。',
            scheduledAt: '2026-06-01 08:00', runCount: 3, failCount: 0,
            tags: ['exam', 'reminder'], createdAt: '2026-02-15',
            successRate: 100, averageDuration: 1100,
            steps: [
                { id: 's7-1', index: 1, name: '查询考试日程', status: 'pending', toolName: 'query_exam_schedule' },
                { id: 's7-2', index: 2, name: '计算倒计时', status: 'pending', toolName: 'calc_countdown' },
                { id: 's7-3', index: 3, name: '推送提醒', status: 'pending', toolName: 'push_reminder' },
            ],
            runLogs: [
                { id: 'r7-3', runNumber: 3, status: 'success', startedAt: '2026-01-15 08:00', completedAt: '2026-01-15 08:00', duration: 1050, stepsCompleted: 3, stepsTotal: 3, triggerType: 'scheduled', summary: '期末考试倒计时 3 天，提醒已发', steps: [] },
            ],
        },
        {
            id: 8, name: 'Club Activity Notifier', type: 'event-triggered', status: 'paused',
            description: '检测到新社团活动报名时自动推送通知。',
            eventSource: 'SUSTech OA', triggerCondition: 'New activity posted',
            lastRunAt: '2026-03-01 10:00', runCount: 7, failCount: 0,
            tags: ['club', 'notify'], createdAt: '2026-02-20',
            successRate: 100, averageDuration: 500,
            steps: [
                { id: 's8-1', index: 1, name: '监听 OA 推送', status: 'pending', toolName: 'listen_oa' },
                { id: 's8-2', index: 2, name: '过滤感兴趣活动', status: 'pending', toolName: 'filter_activity' },
                { id: 's8-3', index: 3, name: '推送通知', status: 'pending', toolName: 'send_notification' },
            ],
            runLogs: [
                { id: 'r8-7', runNumber: 7, status: 'success', startedAt: '2026-03-01 10:00', completedAt: '2026-03-01 10:00', duration: 480, stepsCompleted: 3, stepsTotal: 3, triggerType: 'event', summary: '发现羽毛球社招新活动，已通知', steps: [] },
            ],
        },
        {
            id: 9, name: 'Campus Network Monitor', type: 'monitor', status: 'running',
            description: '监测校园网连接状态，断线时自动重连并告警。',
            monitorTarget: 'Campus WiFi / VPN', lastRunAt: '2026-03-05 14:28',
            nextRunAt: '2026-03-05 14:33', runCount: 1024, failCount: 8,
            tags: ['network', 'monitor'], createdAt: '2026-01-05',
            successRate: 99, averageDuration: 120,
            steps: [
                { id: 's9-1', index: 1, name: '检测网络连通性', status: 'completed', duration: 80, toolName: 'ping_check', output: '{"latency":12,"loss":0}' },
                { id: 's9-2', index: 2, name: '分析网络质量', status: 'running', toolName: 'analyze_quality', startedAt: '2026-03-05 14:28:01' },
                { id: 's9-3', index: 3, name: '异常时告警', status: 'pending', toolName: 'alert_if_down' },
            ],
            runLogs: [
                { id: 'r9-1024', runNumber: 1024, status: 'running', startedAt: '2026-03-05 14:28', stepsCompleted: 1, stepsTotal: 3, triggerType: 'scheduled', steps: [] },
                { id: 'r9-1023', runNumber: 1023, status: 'success', startedAt: '2026-03-05 14:23', completedAt: '2026-03-05 14:23', duration: 115, stepsCompleted: 3, stepsTotal: 3, triggerType: 'scheduled', summary: '网络正常', steps: [] },
            ],
        },
        {
            id: 10, name: 'Shuttle Bus Tracker', type: 'monitor', status: 'failed',
            description: '追踪校园班车实时位置，提前 5 分钟推送到站提醒。',
            monitorTarget: 'Shuttle Bus System', lastRunAt: '2026-03-05 12:00',
            runCount: 156, failCount: 12,
            tags: ['bus', 'transport'], createdAt: '2026-02-01',
            successRate: 92, averageDuration: 2200,
            steps: [
                { id: 's10-1', index: 1, name: '获取班车 GPS 数据', status: 'failed', duration: 3000, toolName: 'fetch_gps', errorMessage: 'GPS API connection timeout after 3000ms', startedAt: '2026-03-05 12:00:00', completedAt: '2026-03-05 12:00:03' },
                { id: 's10-2', index: 2, name: '计算到站时间', status: 'pending', toolName: 'calc_eta' },
                { id: 's10-3', index: 3, name: '推送到站提醒', status: 'pending', toolName: 'push_arrival' },
            ],
            runLogs: [
                { id: 'r10-156', runNumber: 156, status: 'failed', startedAt: '2026-03-05 12:00', completedAt: '2026-03-05 12:00', duration: 3000, stepsCompleted: 0, stepsTotal: 3, triggerType: 'scheduled', errorMessage: 'GPS API connection timeout', steps: [] },
                { id: 'r10-155', runNumber: 155, status: 'success', startedAt: '2026-03-05 11:30', completedAt: '2026-03-05 11:30', duration: 2100, stepsCompleted: 3, stepsTotal: 3, triggerType: 'scheduled', summary: '班车距离 5 分钟，提醒已发', steps: [] },
            ],
        },
    ]
}
