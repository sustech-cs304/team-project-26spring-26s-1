import {
    cancelRun,
    createTask,
    deleteTask,
    disableTask,
    enableTask,
    getRunLogs,
    getTaskRuns,
    getTasks,
    triggerTask,
    updateTask,
} from '@/api/tasks'
import type { EnvVarRef, LogEntry, Run, RunStatus, Task, TaskCreateForm, TaskUpdateForm } from '@/utils/tasks'
import { formatDateTime } from '@/utils/tasks'

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
    { label: 'All', value: 'all' },
    { label: 'Enabled', value: 'enabled' },
    { label: 'Running', value: 'running' },
    { label: 'Disabled', value: 'disabled' },
] as const

export const runStatusFilters = [
    { label: 'All', value: 'all' },
    { label: 'Success', value: 'success' },
    { label: 'Failed', value: 'failed' },
    { label: 'Running', value: 'running' },
    { label: 'Pending', value: 'pending' },
    { label: 'Cancelled', value: 'cancelled' },
] as const

export type StatusFilter = (typeof statusFilters)[number]['value']
export type RunFilter = (typeof runStatusFilters)[number]['value']

export const cronPresets = [
    { label: 'Every hour', cron: '0 * * * *' },
    { label: 'Daily 09:00', cron: '0 9 * * *' },
    { label: 'Weekdays 09:00', cron: '0 9 * * 1-5' },
    { label: 'Every 5 min', cron: '*/5 * * * *' },
]

export function useTaskWorkspace() {
    const tasks = ref<Task[]>([])
    const loading = ref(false)
    const search = ref('')
    const statusFilter = ref<StatusFilter>('all')
    const selectedTaskId = ref<string | null>(null)
    const activeTab = ref<'details' | 'runs'>('details')

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
            ? 'Edit task'
            : editorMode.value === 'duplicate'
                ? 'Duplicate task'
                : 'New task'
    )

    const editorActionLabel = computed(() =>
        editorMode.value === 'edit'
            ? 'Save changes'
            : editorMode.value === 'duplicate'
                ? 'Create copy'
                : 'Create task'
    )

    function showSnackbar(text: string, color: 'success' | 'error' = 'success') {
        snackbar.text = text
        snackbar.color = color
        snackbar.show = true
    }

    function makeEditorForm(task?: Task | null, duplicate = false): TaskEditorForm {
        return {
            name: duplicate && task ? `${task.name} Copy` : task?.name ?? '',
            description: task?.description ?? '',
            execution_mode: task?.execution_mode ?? 'script',
            payload: task?.payload ?? '',
            cron_expression: task?.cron_expression ?? '',
            env_var_refs: task?.env_var_refs.map((item) => ({ ...item })) ?? [],
        }
    }

    function applyEditorForm(task?: Task | null, duplicate = false) {
        Object.assign(editorForm, makeEditorForm(task, duplicate))
    }

    function selectTask(taskId: string) {
        selectedTaskId.value = taskId
        activeTab.value = 'details'
    }

    function openCreate() {
        editorMode.value = 'create'
        applyEditorForm()
        editorDialog.value = true
    }

    function openEdit() {
        if (!selectedTask.value) return
        editorMode.value = 'edit'
        applyEditorForm(selectedTask.value)
        editorDialog.value = true
    }

    function openDuplicate() {
        if (!selectedTask.value) return
        editorMode.value = 'duplicate'
        applyEditorForm(selectedTask.value, true)
        editorDialog.value = true
    }

    function addEnvVar() {
        editorForm.env_var_refs.push({ key: '', secret_ref: '' })
    }

    function removeEnvVar(index: number) {
        editorForm.env_var_refs.splice(index, 1)
    }

    function normalizeEditorPayload(): TaskCreateForm {
        return {
            name: editorForm.name.trim(),
            description: editorForm.description.trim(),
            execution_mode: editorForm.execution_mode,
            payload: editorForm.payload,
            cron_expression: editorForm.cron_expression.trim() || null,
            env_var_refs: editorForm.env_var_refs
                .map((item) => ({ key: item.key.trim(), secret_ref: item.secret_ref.trim() }))
                .filter((item) => item.key),
        }
    }

    async function loadTasksList() {
        loading.value = true
        try {
            const response = await getTasks()
            tasks.value = response.items

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
            showSnackbar('Failed to load tasks', 'error')
        } finally {
            loading.value = false
        }
    }

    async function saveTask() {
        const payload = normalizeEditorPayload()
        if (!payload.name) return

        saving.value = true
        try {
            let savedTask: Task
            if (editorMode.value === 'edit' && selectedTask.value) {
                const updatePayload: TaskUpdateForm = payload
                savedTask = await updateTask(selectedTask.value.id, updatePayload)
                showSnackbar('Task updated')
            } else {
                savedTask = await createTask(payload)
                showSnackbar(editorMode.value === 'duplicate' ? 'Task duplicated' : 'Task created')
            }

            editorDialog.value = false
            await loadTasksList()
            selectedTaskId.value = savedTask.id
        } catch (error) {
            console.error('Failed to save task:', error)
            showSnackbar('Failed to save task', 'error')
        } finally {
            saving.value = false
        }
    }

    async function confirmDelete() {
        if (!selectedTask.value) return

        deleting.value = true
        try {
            await deleteTask(selectedTask.value.id)
            deleteDialog.value = false
            showSnackbar('Task deleted')
            await loadTasksList()
        } catch (error) {
            console.error('Failed to delete task:', error)
            showSnackbar('Failed to delete task', 'error')
        } finally {
            deleting.value = false
        }
    }

    async function toggleTaskStatus() {
        if (!selectedTask.value) return
        try {
            if (selectedTask.value.status === 'disabled') {
                await enableTask(selectedTask.value.id)
                showSnackbar('Task enabled')
            } else {
                await disableTask(selectedTask.value.id)
                showSnackbar('Task disabled')
            }
            await loadTasksList()
        } catch (error) {
            console.error('Failed to toggle task:', error)
            showSnackbar('Failed to update task status', 'error')
        }
    }

    async function triggerNow() {
        if (!selectedTask.value) return
        triggering.value = true
        try {
            await triggerTask(selectedTask.value.id)
            showSnackbar('Task triggered')
            activeTab.value = 'runs'
            await Promise.all([loadTasksList(), loadRuns()])
        } catch (error) {
            console.error('Failed to trigger task:', error)
            showSnackbar('Failed to trigger task', 'error')
        } finally {
            triggering.value = false
        }
    }

    async function loadRuns() {
        if (!selectedTask.value) return
        runsLoading.value = true
        try {
            const response = await getTaskRuns(selectedTask.value.id, {
                page: 1,
                page_size: 20,
                status: runStatusFilter.value === 'all' ? undefined : runStatusFilter.value as RunStatus,
            })
            runs.value = response.items

            if (!runs.value.length) {
                selectedRunId.value = null
                return
            }

            const firstRun = runs.value[0]
            if ((!selectedRunId.value || !runs.value.some((run) => run.id === selectedRunId.value)) && firstRun) {
                selectedRunId.value = firstRun.id
            }
        } catch (error) {
            console.error('Failed to load runs:', error)
            showSnackbar('Failed to load runs', 'error')
        } finally {
            runsLoading.value = false
        }
    }

    function selectRun(runId: string) {
        selectedRunId.value = runId
    }

    async function cancelSelectedRun() {
        if (!selectedRun.value || (selectedRun.value.status !== 'pending' && selectedRun.value.status !== 'running')) return
        try {
            await cancelRun(selectedRun.value.id)
            showSnackbar('Run cancelled')
            await loadRuns()
        } catch (error) {
            console.error('Failed to cancel run:', error)
            showSnackbar('Failed to cancel run', 'error')
        }
    }

    function formatLogLine(log: LogEntry) {
        const pieces = [formatDateTime(log.timestamp)]
        if (log.log_type === 'tool_call') pieces.push(`[tool] ${log.tool_name ?? 'unknown'}`)
        else if (log.content) pieces.push(String(log.content))
        else if (log.metadata?.exit_code != null) pieces.push(`Exited with code ${log.metadata.exit_code}`)
        else pieces.push(log.log_type)
        return pieces.join('  ')
    }

    watch(selectedRunId, async (runId) => {
        if (!runId || logCache.value[runId]) return
        logsLoading.value = true
        try {
            const logs = await getRunLogs(runId)
            logCache.value[runId] = logs.map(formatLogLine)
        } catch (error) {
            console.error('Failed to load logs:', error)
            logCache.value[runId] = []
            showSnackbar('Failed to load logs', 'error')
        } finally {
            logsLoading.value = false
        }
    })

    watch(activeTab, (tab) => {
        if (tab === 'runs' && selectedTask.value) loadRuns()
    })

    watch(selectedTaskId, () => {
        runs.value = []
        selectedRunId.value = null
        logCache.value = {}
        if (activeTab.value === 'runs' && selectedTask.value) loadRuns()
    })

    watch(runStatusFilter, () => {
        if (activeTab.value === 'runs' && selectedTask.value) {
            selectedRunId.value = null
            logCache.value = {}
            loadRuns()
        }
    })

    onMounted(() => {
        loadTasksList()
    })

    return {
        activeTab,
        addEnvVar,
        cancelSelectedRun,
        confirmDelete,
        cronPresets,
        deleteDialog,
        deleting,
        editorActionLabel,
        editorDialog,
        editorForm,
        editorTitle,
        filteredTasks,
        loading,
        logsLoading,
        openCreate,
        openDuplicate,
        openEdit,
        removeEnvVar,
        runStatusFilter,
        runs,
        runsLoading,
        saveTask,
        saving,
        search,
        selectRun,
        selectedRun,
        selectedRunId,
        selectedRunLogs,
        selectedTask,
        selectedTaskId,
        selectTask,
        snackbar,
        statusFilter,
        tasks,
        toggleTaskStatus,
        triggerNow,
        triggering,
    }
}
