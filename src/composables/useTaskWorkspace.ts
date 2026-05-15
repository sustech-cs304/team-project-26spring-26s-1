import {
    cancelRun,
    createTask,
    deleteTask,
    deleteEnvVar,
    disableTask,
    enableTask,
    getEnvVars,
    getRunLogs,
    getTaskRuns,
    getTasks,
    triggerTask,
    updateTask,
    upsertEnvVar,
} from '@/api/tasks'
import type { EnvVarRef, LogEntry, Run, RunStatus, Task, TaskCreateForm, TaskUpdateForm } from '@/utils/tasks'
import { formatDateTime, parseTaskDateTime, validateEnvVarKey } from '@/utils/tasks'

type EditorMode = 'create' | 'edit' | 'duplicate'

export interface TaskEditorForm {
    name: string
    description: string
    execution_mode: Task['execution_mode']
    payload: string
    cron_expression: string
    env_var_refs: EnvVarRef[]
}

export const statusFilters = [
    { label: '全部', value: 'all' },
    { label: '启用中', value: 'enabled' },
    { label: '运行中', value: 'running' },
    { label: '已禁用', value: 'disabled' },
] as const

export const runStatusFilters = [
    { label: '全部', value: 'all' },
    { label: '成功', value: 'success' },
    { label: '失败', value: 'failed' },
    { label: '运行中', value: 'running' },
    { label: '等待中', value: 'pending' },
    { label: '已取消', value: 'cancelled' },
] as const

export type StatusFilter = (typeof statusFilters)[number]['value']
export type RunFilter = (typeof runStatusFilters)[number]['value']

export const cronPresets = [
    { label: '每小时', cron: '0 * * * *' },
    { label: '工作日 09:00', cron: '0 9 * * 1-5' },
    { label: '每 5 分钟', cron: '*/5 * * * *' },
]

const TASK_POLL_INTERVAL_MS = 3_000

function getRunSortTime (run: Run): number {
    return parseTaskDateTime(run.started_at)?.getTime()
        ?? parseTaskDateTime(run.finished_at)?.getTime()
        ?? 0
}

function sortRunsByTimeDesc (items: Run[]): Run[] {
    return [...items].sort((a, b) => {
        const diff = getRunSortTime(b) - getRunSortTime(a)
        if (diff !== 0) return diff
        return a.id.localeCompare(b.id)
    })
}

export function useTaskWorkspace () {
    const tasks = ref<Task[]>([])
    const loading = ref(false)
    const search = ref('')
    const statusFilter = ref<StatusFilter>('all')
    const selectedTaskId = ref<string | null>(null)

    const triggering = ref(false)
    const saving = ref(false)
    const deleting = ref(false)
    const editorDialog = ref(false)
    const deleteDialog = ref(false)
    const editorMode = ref<EditorMode>('create')

    const runs = ref<Run[]>([])
    const runsLoading = ref(false)
    const runStatusFilter = ref<RunFilter>('all')
    const selectedRunId = ref<string | null>(null)
    const logCache = ref<Record<string, string[]>>({})
    const logsLoading = ref(false)

    const envVars = ref<EnvVarRef[]>([])
    const envVarsLoading = ref(false)
    const envVarSaving = ref(false)
    const deletingEnvKey = ref<string | null>(null)
    const latestEnvKey = ref<string | null>(null)

    const snackbar = reactive({
        show: false,
        text: '',
        color: 'success',
    })

    const editorForm = reactive<TaskEditorForm>({
        name: '',
        description: '',
        execution_mode: 'script',
        payload: '',
        cron_expression: '',
        env_var_refs: [],
    })

    const editorInitialSnapshot = ref<TaskEditorForm>(makeEditorForm())
    let pollTimer: ReturnType<typeof setInterval> | null = null

    const filteredTasks = computed(() => {
        const query = search.value.trim().toLowerCase()

        return tasks.value.filter((task) => {
            const matchQuery = !query
                || task.name.toLowerCase().includes(query)
                || (task.description ?? '').toLowerCase().includes(query)

            const matchStatus = statusFilter.value === 'all' || task.status === statusFilter.value
            return matchQuery && matchStatus
        })
    })

    const selectedTask = computed(() =>
        tasks.value.find((task) => task.id === selectedTaskId.value) ?? null
    )

    const selectedRun = computed(() =>
        runs.value.find((run) => run.id === selectedRunId.value) ?? null
    )

    const selectedRunLogs = computed(() =>
        selectedRunId.value ? (logCache.value[selectedRunId.value] ?? []) : []
    )

    const editorTitle = computed(() =>
        editorMode.value === 'edit'
            ? '编辑任务'
            : editorMode.value === 'duplicate'
                ? '复制任务'
                : '新建任务'
    )

    const editorActionLabel = computed(() =>
        editorMode.value === 'edit'
            ? '保存修改'
            : editorMode.value === 'duplicate'
                ? '创建副本'
                : '创建任务'
    )

    function showSnackbar (text: string, color: 'success' | 'error' = 'success') {
        snackbar.text = text
        snackbar.color = color
        snackbar.show = true
    }

    async function loadEnvVarList () {
        envVarsLoading.value = true
        try {
            const result = await getEnvVars()

            if (!Array.isArray(result)) {
                throw new Error('Invalid env vars response payload')
            }

            envVars.value = result
        } catch (error) {
            console.error('Failed to load environment variables:', error)
            envVars.value = []
            showSnackbar('加载环境变量失败', 'error')
        } finally {
            envVarsLoading.value = false
        }
    }

    async function ensureEnvVarsLoaded () {
        if (envVars.value.length || envVarsLoading.value) return
        await loadEnvVarList()
    }

    async function saveEnvVar (payload?: { key: string, value: string }) {
        const key = payload?.key.trim() ?? ''
        const value = payload?.value.trim() ?? ''
        if (!key || !value || envVarSaving.value) return

        const keyError = validateEnvVarKey(key)
        if (keyError) {
            showSnackbar(keyError, 'error')
            return
        }

        envVarSaving.value = true
        try {
            const saved = await upsertEnvVar({ key, value })
            latestEnvKey.value = saved.key
            await loadEnvVarList()
            showSnackbar('环境变量已保存')
        } catch (error) {
            console.error('Failed to save environment variable:', error)
            showSnackbar('保存环境变量失败', 'error')
        } finally {
            envVarSaving.value = false
        }
    }

    async function removeEnvVarEntry (key: string) {
        deletingEnvKey.value = key
        try {
            await deleteEnvVar(key)
            envVars.value = envVars.value.filter((item) => item.key !== key)
            showSnackbar('环境变量已删除')
        } catch (error) {
            console.error('Failed to delete environment variable:', error)
            showSnackbar('删除环境变量失败', 'error')
        } finally {
            deletingEnvKey.value = null
        }
    }

    function makeEditorForm (task?: Task | null, duplicate = false): TaskEditorForm {
        return {
            name: duplicate && task ? `${task.name} Copy` : task?.name ?? '',
            description: task?.description ?? '',
            execution_mode: task?.execution_mode ?? 'script',
            payload: task?.payload ?? '',
            cron_expression: task?.cron_expression ?? '',
            env_var_refs: task?.env_var_refs.map((item) => ({ ...item })) ?? [],
        }
    }

    function cloneEditorForm (form: TaskEditorForm): TaskEditorForm {
        return {
            name: form.name,
            description: form.description,
            execution_mode: form.execution_mode,
            payload: form.payload,
            cron_expression: form.cron_expression,
            env_var_refs: form.env_var_refs.map((item) => ({ ...item })),
        }
    }

    function normalizeFormForCompare (form: TaskEditorForm) {
        return {
            name: form.name.trim(),
            description: form.description.trim(),
            execution_mode: form.execution_mode,
            payload: form.payload,
            cron_expression: form.cron_expression.trim(),
            env_var_refs: form.env_var_refs.map((item) => ({
                key: item.key.trim(),
            })),
        }
    }

    const hasEditorChanges = computed(() => {
        const current = normalizeFormForCompare(editorForm)
        const initial = normalizeFormForCompare(editorInitialSnapshot.value)
        return JSON.stringify(current) !== JSON.stringify(initial)
    })

    function applyEditorForm (task?: Task | null, duplicate = false) {
        const form = makeEditorForm(task, duplicate)
        editorInitialSnapshot.value = cloneEditorForm(form)
        Object.assign(editorForm, form)
    }

    function selectTask (taskId: string) {
        selectedTaskId.value = taskId
    }

    function openCreate () {
        editorMode.value = 'create'
        applyEditorForm()
        editorDialog.value = true
    }

    function openEdit () {
        if (!selectedTask.value) return
        editorMode.value = 'edit'
        applyEditorForm(selectedTask.value)
        editorDialog.value = true
    }

    function openDuplicate () {
        if (!selectedTask.value) return
        editorMode.value = 'duplicate'
        applyEditorForm(selectedTask.value, true)
        editorDialog.value = true
    }

    function addEnvVar () {
        editorForm.env_var_refs.push({ key: '' })
    }

    function removeEnvVar (index: number) {
        editorForm.env_var_refs.splice(index, 1)
    }

    function normalizeEditorPayload (): TaskCreateForm {
        return {
            name: editorForm.name.trim(),
            description: editorForm.description.trim(),
            execution_mode: editorForm.execution_mode,
            payload: editorForm.payload,
            cron_expression: editorForm.cron_expression.trim() || null,
            env_var_refs: editorForm.env_var_refs
                .map((item) => ({ key: item.key.trim() }))
                .filter((item) => item.key),
        }
    }

    async function loadTasksList (options?: { silent?: boolean }) {
        const silent = options?.silent ?? false
        if (!silent) loading.value = true
        try {
            const response = await getTasks()
            const items = Array.isArray(response?.items) ? response.items : []
            tasks.value = items

            if (!tasks.value.length) {
                selectedTaskId.value = null
                return
            }

            const firstTask = tasks.value[0]
            if ((!selectedTaskId.value || !tasks.value.some((task) => task.id === selectedTaskId.value)) && firstTask) {
                selectedTaskId.value = firstTask.id
            }
        } catch (error) {
            console.error('Failed to load tasks:', error)
            tasks.value = []
            selectedTaskId.value = null
            if (!silent) showSnackbar('加载任务失败', 'error')
        } finally {
            if (!silent) loading.value = false
        }
    }

    async function saveTask () {
        const payload = normalizeEditorPayload()
        if (!payload.name) return false

        saving.value = true
        try {
            let savedTask: Task
            if (editorMode.value === 'edit' && selectedTask.value) {
                const updatePayload: TaskUpdateForm = payload
                savedTask = await updateTask(selectedTask.value.id, updatePayload)
                showSnackbar('任务已更新')
            } else {
                savedTask = await createTask(payload)
                showSnackbar(editorMode.value === 'duplicate' ? '任务已复制' : '任务已创建')
            }

            editorDialog.value = false
            await loadTasksList()
            selectedTaskId.value = savedTask.id
            editorInitialSnapshot.value = cloneEditorForm(editorForm)
            return true
        } catch (error) {
            console.error('Failed to save task:', error)
            showSnackbar('保存任务失败', 'error')
            return false
        } finally {
            saving.value = false
        }
    }

    async function confirmDelete () {
        if (!selectedTask.value) return

        deleting.value = true
        try {
            await deleteTask(selectedTask.value.id)
            deleteDialog.value = false
            showSnackbar('任务已删除')
            await loadTasksList()
        } catch (error) {
            console.error('Failed to delete task:', error)
            showSnackbar('删除任务失败', 'error')
        } finally {
            deleting.value = false
        }
    }

    async function toggleTaskStatus () {
        if (!selectedTask.value) return
        try {
            if (selectedTask.value.status === 'disabled') {
                await enableTask(selectedTask.value.id)
                showSnackbar('任务已启用')
            } else {
                await disableTask(selectedTask.value.id)
                showSnackbar('任务已禁用')
            }
            await loadTasksList()
        } catch (error) {
            console.error('Failed to toggle task:', error)
            showSnackbar('更新任务状态失败', 'error')
        }
    }

    async function triggerNow () {
        if (!selectedTask.value) return
        triggering.value = true
        try {
            await triggerTask(selectedTask.value.id)
            showSnackbar('任务已触发')
            await Promise.all([loadTasksList(), loadRuns()])
        } catch (error) {
            console.error('Failed to trigger task:', error)
            showSnackbar('触发任务失败', 'error')
        } finally {
            triggering.value = false
        }
    }

    async function loadRuns (options?: { silent?: boolean }) {
        const silent = options?.silent ?? false
        if (!selectedTask.value) return
        if (!silent) runsLoading.value = true
        try {
            const response = await getTaskRuns(selectedTask.value.id, {
                page: 1,
                page_size: 20,
                status: runStatusFilter.value === 'all' ? undefined : runStatusFilter.value as RunStatus,
            })
            const items = Array.isArray(response?.items) ? response.items : []
            const sortedItems = sortRunsByTimeDesc(items)
            runs.value = sortedItems

            if (!runs.value.length) {
                selectedRunId.value = null
                return
            }

            const latestRun = runs.value[0]
            if ((!selectedRunId.value || !runs.value.some((run) => run.id === selectedRunId.value)) && latestRun) {
                selectedRunId.value = latestRun.id
            }
        } catch (error) {
            console.error('Failed to load runs:', error)
            runs.value = []
            selectedRunId.value = null
            if (!silent) showSnackbar('加载运行记录失败', 'error')
        } finally {
            if (!silent) runsLoading.value = false
        }
    }

    async function loadRunLogs (runId: string, options?: { silent?: boolean; force?: boolean }) {
        const silent = options?.silent ?? false
        const force = options?.force ?? false
        if (!runId) return
        if (!force && logCache.value[runId]) return

        if (!silent) logsLoading.value = true
        try {
            const logs = await getRunLogs(runId)
            logCache.value[runId] = logs.map(formatLogLine)
        } catch (error) {
            console.error('Failed to load logs:', error)
            logCache.value[runId] = []
            if (!silent) showSnackbar('加载日志失败', 'error')
        } finally {
            if (!silent) logsLoading.value = false
        }
    }

    function selectRun (runId: string) {
        selectedRunId.value = runId
    }

    async function cancelSelectedRun () {
        if (!selectedRun.value || (selectedRun.value.status !== 'pending' && selectedRun.value.status !== 'running')) return
        try {
            await cancelRun(selectedRun.value.id)
            showSnackbar('运行已取消')
            await loadRuns()
        } catch (error) {
            console.error('Failed to cancel run:', error)
            showSnackbar('取消运行失败', 'error')
        }
    }

    function formatLogLine (log: LogEntry) {
        const pieces = [formatDateTime(log.timestamp)]
        if (log.log_type === 'tool_call') pieces.push(`[tool] ${log.tool_name ?? 'unknown'}`)
        else if (log.content) pieces.push(String(log.content))
        else if (log.metadata?.exit_code != null) pieces.push(`Exited with code ${log.metadata.exit_code}`)
        else pieces.push(log.log_type)
        return pieces.join('  ')
    }

    watch(selectedRunId, async (runId) => {
        if (!runId) return
        await loadRunLogs(runId)
    })

    watch(() => selectedTask.value?.id ?? null, (taskId) => {
        runs.value = []
        selectedRunId.value = null
        logCache.value = {}
        if (taskId) loadRuns()
    })

    watch(runStatusFilter, () => {
        if (selectedTask.value) {
            selectedRunId.value = null
            logCache.value = {}
            loadRuns()
        }
    })

    async function pollVisibleTaskData () {
        if (document.hidden) return

        await loadTasksList({ silent: true })

        if (selectedTask.value) {
            await loadRuns({ silent: true })
            if (selectedRunId.value) {
                await loadRunLogs(selectedRunId.value, { silent: true, force: true })
            }
        }
    }

    onMounted(() => {
        void loadTasksList()
        pollTimer = setInterval(() => {
            void pollVisibleTaskData()
        }, TASK_POLL_INTERVAL_MS)
    })

    onBeforeUnmount(() => {
        if (pollTimer) {
            clearInterval(pollTimer)
            pollTimer = null
        }
    })

    return {
        addEnvVar,
        cancelSelectedRun,
        confirmDelete,
        cronPresets,
        deleteDialog,
        deleting,
        deletingEnvKey,
        editorActionLabel,
        editorDialog,
        editorForm,
        editorTitle,
        ensureEnvVarsLoaded,
        envVarSaving,
        envVars,
        envVarsLoading,
        filteredTasks,
        hasEditorChanges,
        latestEnvKey,
        loadEnvVarList,
        loading,
        logsLoading,
        openCreate,
        openDuplicate,
        openEdit,
        removeEnvVarEntry,
        removeEnvVar,
        runStatusFilter,
        runs,
        runsLoading,
        saveTask,
        saveEnvVar,
        saving,
        search,
        selectRun,
        selectedRun,
        selectedRunId,
        selectedRunLogs,
        selectedTask,
        selectedTaskId,
        selectTask,
        showSnackbar,
        snackbar,
        statusFilter,
        tasks,
        toggleTaskStatus,
        triggerNow,
        triggering,
    }
}
