<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0">

        <!-- 统计栏 -->
        <v-sheet class="px-6 py-4 border-b flex-shrink-0" color="transparent">
            <div class="d-flex align-center justify-space-between">
                <!-- 左侧统计指标 -->
                <div class="d-flex align-center ga-4">
                    <!-- Total -->
                    <div class="d-flex align-center ga-2">
                        <span class="text-subtitle-2 font-weight-bold" style="font-variant-numeric: tabular-nums;">
                            {{ tasks.length }}
                        </span>
                        <span class="text-caption text-medium-emphasis">Total</span>
                    </div>
                    <v-divider vertical style="height:16px;" />
                    <!-- Running -->
                    <div class="d-flex align-center ga-2">
                        <span class="status-dot dot-running" />
                        <span class="text-subtitle-2 font-weight-bold text-success">{{ countByStatus('running')
                            }}</span>
                        <span class="text-caption text-medium-emphasis">Running</span>
                    </div>
                    <v-divider vertical style="height:16px;" />
                    <!-- Paused -->
                    <div class="d-flex align-center ga-2">
                        <span class="status-dot" style="background:rgb(var(--v-theme-warning))" />
                        <span class="text-subtitle-2 font-weight-bold text-warning">{{ countByStatus('paused') }}</span>
                        <span class="text-caption text-medium-emphasis">Paused</span>
                    </div>
                    <v-divider vertical style="height:16px;" />
                    <!-- Failed -->
                    <div class="d-flex align-center ga-2">
                        <span class="status-dot" style="background:rgb(var(--v-theme-error))" />
                        <span class="text-subtitle-2 font-weight-bold text-error">{{ countByStatus('failed') }}</span>
                        <span class="text-caption text-medium-emphasis">Failed</span>
                    </div>
                </div>
                <!-- 右侧新建按钮 -->
                <v-btn size="small" color="primary" @click="openCreateDialog">
                    <v-icon size="14" class="mr-1">mdi-plus</v-icon>
                    New Task
                </v-btn>
            </div>
        </v-sheet>

        <!-- 筛选栏 -->
        <v-sheet class="px-6 py-3 border-b flex-shrink-0" color="transparent">
            <div class="d-flex flex-wrap align-center ga-2">
                <!-- 搜索框 -->
                <div class="flex-grow-1 position-relative" style="min-width:160px;">
                    <v-icon size="14" class="position-absolute text-medium-emphasis"
                        style="top:50%;transform:translateY(-50%);left:10px;z-index:1;">
                        mdi-magnify
                    </v-icon>
                    <v-text-field v-model="search" density="compact" variant="outlined" placeholder="Search tasks..."
                        hide-details style="font-size:12px;" :style="{ '--v-input-padding-start': '32px' }"
                        class="search-input" />
                </div>
                <!-- 类型筛选 -->
                <div class="d-flex ga-1">
                    <button v-for="chip in typeChips" :key="chip.value" class="filter-chip"
                        :class="{ active: typeFilter === chip.value }" @click="typeFilter = chip.value">
                        <v-icon v-if="chip.icon" :size="12" class="mr-1">{{ chip.icon }}</v-icon>
                        {{ chip.label }}
                    </button>
                </div>
                <!-- 状态筛选 -->
                <div class="d-flex ga-1">
                    <button v-for="chip in statusChips" :key="chip.value" class="filter-chip"
                        :class="{ active: statusFilter === chip.value }" @click="statusFilter = chip.value">
                        <span v-if="chip.color" class="status-dot mr-1"
                            :class="{ 'dot-running': chip.value === 'running' }"
                            :style="chip.value !== 'running' ? { background: chip.color } : {}" />
                        {{ chip.label }}
                    </button>
                </div>
            </div>
        </v-sheet>

        <!-- 任务列表 -->
        <v-sheet color="transparent" class="flex-grow-1 overflow-y-auto">
            <div class="pa-6">
                <!-- 空状态 -->
                <div v-if="filteredTasks.length === 0" class="d-flex flex-column align-center justify-center py-16">
                    <v-icon size="32" style="opacity:0.4;" class="text-medium-emphasis mb-1">mdi-list-status</v-icon>
                    <span class="text-body-2 text-medium-emphasis mt-1">No tasks found</span>
                    <span class="text-caption text-disabled mt-3">Try adjusting your filters or create a new task</span>
                </div>

                <!-- 任务卡片列表 -->
                <div v-else class="d-flex flex-column ga-3">
                    <div v-for="task in filteredTasks" :key="task.id" class="task-card"
                        :class="`task-card--${task.status}`">
                        <!-- 第一行 -->
                        <div class="d-flex align-start ga-3">
                            <!-- 类型图标 -->
                            <div class="task-type-icon flex-shrink-0" :class="`task-type-icon--${task.status}`">
                                <v-icon :size="16" :color="typeIconColor(task.type)">{{ typeIcon(task.type) }}</v-icon>
                            </div>
                            <!-- 名称区 -->
                            <div class="flex-grow-1 min-width-0">
                                <div class="d-flex align-center ga-1 flex-wrap">
                                    <span class="text-body-2 font-weight-bold text-truncate">{{ task.name }}</span>
                                    <v-chip :color="statusColor(task.status)" variant="outlined" size="x-small"
                                        density="compact" style="font-size:9px;height:18px;">
                                        <span class="status-dot mr-1"
                                            :class="{ 'dot-running': task.status === 'running' }"
                                            :style="task.status !== 'running' ? { background: statusColorRaw(task.status) } : {}" />
                                        {{ task.status }}
                                    </v-chip>
                                    <v-chip variant="tonal" size="x-small" density="compact"
                                        style="font-size:9px;height:18px;">{{ task.type }}</v-chip>
                                </div>
                                <div v-if="task.description" class="text-caption text-medium-emphasis mt-1"
                                    style="line-height:1.625;">
                                    {{ task.description }}
                                </div>
                            </div>
                            <!-- 操作区 -->
                            <div class="d-flex align-center ga-1 flex-shrink-0">
                                <v-switch :model-value="task.status !== 'paused' && task.status !== 'failed'"
                                    density="compact" hide-details color="success"
                                    style="transform:scale(0.75);transform-origin:right center;"
                                    @change="toggleTask(task)" />
                                <v-menu location="bottom end">
                                    <template #activator="{ props }">
                                        <v-btn v-bind="props" icon variant="text" size="x-small" width="28" height="28">
                                            <v-icon size="16">mdi-dots-horizontal</v-icon>
                                        </v-btn>
                                    </template>
                                    <v-list density="compact" min-width="140">
                                        <v-list-item v-if="task.status === 'running' || task.status === 'paused'"
                                            @click="togglePause(task)">
                                            <template #prepend>
                                                <v-icon size="14">{{ task.status === 'running' ? 'mdi-pause' :
                                                    'mdi-play' }}</v-icon>
                                            </template>
                                            <v-list-item-title class="text-caption">
                                                {{ task.status === 'running' ? 'Pause' : 'Resume' }}
                                            </v-list-item-title>
                                        </v-list-item>
                                        <v-list-item @click="openEditDialog(task)">
                                            <template #prepend><v-icon size="14">mdi-pencil</v-icon></template>
                                            <v-list-item-title class="text-caption">Edit</v-list-item-title>
                                        </v-list-item>
                                        <v-divider />
                                        <v-list-item @click="openDeleteDialog(task)">
                                            <template #prepend><v-icon size="14"
                                                    color="error">mdi-delete</v-icon></template>
                                            <v-list-item-title
                                                class="text-caption text-error">Delete</v-list-item-title>
                                        </v-list-item>
                                    </v-list>
                                </v-menu>
                            </div>
                        </div>

                        <!-- 第二行：元数据 -->
                        <div class="d-flex flex-wrap align-center ga-1 mt-2" style="padding-left:48px;">
                            <!-- 类型专属元数据 -->
                            <template v-if="task.type === 'recurring' && task.intervalLabel">
                                <span class="meta-item">
                                    <v-icon size="12" class="text-medium-emphasis">mdi-refresh</v-icon>
                                    <span class="text-medium-emphasis" style="font-size:11px;">{{ task.intervalLabel
                                        }}</span>
                                </span>
                            </template>
                            <template v-if="task.type === 'scheduled' && task.scheduledAt">
                                <span class="meta-item">
                                    <v-icon size="12" class="text-medium-emphasis">mdi-clock-outline</v-icon>
                                    <span class="text-medium-emphasis" style="font-size:11px;">{{ task.scheduledAt
                                        }}</span>
                                </span>
                            </template>
                            <template v-if="task.type === 'event-triggered' && task.eventSource">
                                <span class="meta-item">
                                    <v-icon size="12" class="text-medium-emphasis">mdi-lightning-bolt</v-icon>
                                    <span class="text-medium-emphasis" style="font-size:11px;">{{ task.eventSource
                                        }}</span>
                                </span>
                            </template>
                            <template v-if="task.type === 'monitor' && task.monitorTarget">
                                <span class="meta-item">
                                    <v-icon size="12" class="text-medium-emphasis">mdi-eye-outline</v-icon>
                                    <span class="text-medium-emphasis" style="font-size:11px;">{{ task.monitorTarget
                                        }}</span>
                                </span>
                            </template>
                            <template v-if="task.lastRunAt">
                                <span class="meta-item">
                                    <v-icon size="12" class="text-medium-emphasis">mdi-clock-outline</v-icon>
                                    <span class="text-medium-emphasis" style="font-size:11px;">Last: {{ task.lastRunAt
                                        }}</span>
                                </span>
                            </template>
                            <template v-if="task.nextRunAt">
                                <span class="meta-item">
                                    <v-icon size="12" class="text-medium-emphasis">mdi-timer-outline</v-icon>
                                    <span class="text-medium-emphasis" style="font-size:11px;">Next: {{ task.nextRunAt
                                        }}</span>
                                </span>
                            </template>
                            <template v-if="task.runCount != null">
                                <span class="meta-item">
                                    <v-icon size="12" class="text-medium-emphasis">mdi-pound</v-icon>
                                    <span class="text-medium-emphasis" style="font-size:11px;">
                                        {{ task.runCount }} runs{{ task.failCount ? ` / ${task.failCount} fails` : '' }}
                                    </span>
                                </span>
                            </template>
                            <!-- 标签 -->
                            <template v-if="task.tags && task.tags.length">
                                <v-chip v-for="tag in task.tags" :key="tag" variant="tonal" size="x-small"
                                    density="compact" style="font-size:9px;height:16px;">{{ tag }}</v-chip>
                            </template>
                        </div>
                    </div>
                </div>
            </div>
        </v-sheet>

        <!-- 新建/编辑弹窗 -->
        <v-dialog v-model="dialogOpen" max-width="512" scrollable>
            <v-card rounded="lg" class="border">
                <v-card-title class="d-flex align-center ga-2 px-4 pt-4 pb-2">
                    <v-icon size="16" color="primary">{{ editingTask ? 'mdi-pencil' : 'mdi-plus-circle' }}</v-icon>
                    <span class="text-body-2 font-weight-bold">{{ editingTask ? 'Edit Task' : 'Create New Task'
                        }}</span>
                </v-card-title>
                <v-divider />
                <v-card-text class="pa-4" style="max-height:70vh;overflow-y:auto;">
                    <div class="d-flex flex-column ga-4">
                        <!-- 任务类型选择 -->
                        <div>
                            <div class="text-caption text-medium-emphasis mb-2">Task Type</div>
                            <div class="d-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                                <div v-for="t in taskTypes" :key="t.value" class="type-option"
                                    :class="{ 'type-option--active': form.type === t.value }"
                                    @click="form.type = t.value">
                                    <v-icon :size="16" :color="form.type === t.value ? 'primary' : 'medium-emphasis'">{{
                                        t.icon
                                        }}</v-icon>
                                    <div>
                                        <div class="text-caption font-weight-bold"
                                            :class="form.type === t.value ? 'text-primary' : ''">{{ t.label }}</div>
                                        <div class="text-medium-emphasis" style="font-size:10px;">{{ t.desc }}</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <!-- 任务名称 -->
                        <div>
                            <div class="text-caption text-medium-emphasis mb-1">Task Name</div>
                            <v-text-field v-model="form.name" density="compact" variant="outlined"
                                placeholder="e.g. Library Seat Monitor" hide-details />
                        </div>
                        <!-- 描述 -->
                        <div>
                            <div class="text-caption text-medium-emphasis mb-1">Description</div>
                            <v-textarea v-model="form.description" density="compact" variant="outlined"
                                placeholder="Describe what this task does..." hide-details :rows="3" no-resize
                                style="min-height:72px;" />
                        </div>
                        <!-- 类型专属配置 -->
                        <div class="type-config-block">
                            <div class="text-caption font-weight-bold text-medium-emphasis mb-2"
                                style="font-size:10px;letter-spacing:0.08em;text-transform:uppercase;">
                                {{ form.type }} Configuration
                            </div>
                            <!-- Recurring -->
                            <template v-if="form.type === 'recurring'">
                                <div class="text-caption text-medium-emphasis mb-1">Cron Expression</div>
                                <v-text-field v-model="form.cron" density="compact" variant="outlined"
                                    placeholder="0 9 * * *" hide-details class="mb-3"
                                    style="font-family:monospace;font-size:12px;" />
                                <div class="text-caption text-medium-emphasis mb-1">Readable Description</div>
                                <v-text-field v-model="form.intervalLabel" density="compact" variant="outlined"
                                    placeholder="Every day at 09:00" hide-details />
                            </template>
                            <!-- Scheduled -->
                            <template v-else-if="form.type === 'scheduled'">
                                <div class="text-caption text-medium-emphasis mb-1">Execute At</div>
                                <v-text-field v-model="form.scheduledAt" type="datetime-local" density="compact"
                                    variant="outlined" hide-details />
                            </template>
                            <!-- Event -->
                            <template v-else-if="form.type === 'event-triggered'">
                                <div class="text-caption text-medium-emphasis mb-1">Event Source</div>
                                <v-select v-model="form.eventSource" density="compact" variant="outlined"
                                    :items="eventSources" hide-details class="mb-3" />
                                <div class="text-caption text-medium-emphasis mb-1">Trigger Condition</div>
                                <v-text-field v-model="form.triggerCondition" density="compact" variant="outlined"
                                    placeholder="e.g. New email received" hide-details />
                            </template>
                            <!-- Monitor -->
                            <template v-else-if="form.type === 'monitor'">
                                <div class="text-caption text-medium-emphasis mb-1">Monitor Target</div>
                                <v-text-field v-model="form.monitorTarget" density="compact" variant="outlined"
                                    placeholder="e.g. Library Floor 3 Area A" hide-details class="mb-3" />
                                <div class="text-caption text-medium-emphasis mb-1">Poll Interval</div>
                                <v-select v-model="form.pollInterval" density="compact" variant="outlined"
                                    :items="pollIntervals" hide-details />
                            </template>
                        </div>
                        <!-- 标签 -->
                        <div>
                            <div class="text-caption text-medium-emphasis mb-2">Tags</div>
                            <div class="d-flex flex-wrap align-center ga-1">
                                <v-chip v-for="(tag, i) in form.tags" :key="tag" variant="tonal" size="x-small" closable
                                    style="font-size:10px;" @click:close="form.tags.splice(i, 1)">{{ tag }}</v-chip>
                                <input v-model="tagInput" class="tag-input" placeholder="Add tag..."
                                    @keydown.enter.prevent="addTag" />
                            </div>
                        </div>
                    </div>
                </v-card-text>
                <v-divider />
                <v-card-actions class="px-4 py-3 ga-2 justify-end">
                    <v-btn variant="outlined" size="small" @click="dialogOpen = false">Cancel</v-btn>
                    <v-btn color="primary" size="small" :disabled="!form.name.trim()" @click="saveTask">
                        {{ editingTask ? 'Save Changes' : 'Create Task' }}
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>

        <!-- 删除确认弹窗 -->
        <v-dialog v-model="deleteDialogOpen" max-width="360">
            <v-card rounded="lg">
                <v-card-title class="d-flex align-center ga-2 px-4 pt-4 pb-2">
                    <v-icon size="16" color="error">mdi-alert-triangle</v-icon>
                    <span class="text-body-2 font-weight-bold">Delete Task</span>
                </v-card-title>
                <v-card-text class="text-body-2 px-4 py-2">
                    Are you sure you want to delete <strong>{{ deletingTask?.name }}</strong>? This action cannot be
                    undone.
                </v-card-text>
                <v-card-actions class="px-4 py-3 ga-2 justify-end">
                    <v-btn variant="outlined" size="small" @click="deleteDialogOpen = false">Cancel</v-btn>
                    <v-btn color="error" size="small" @click="confirmDelete">Delete</v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>

    </v-container>
</template>

<script setup lang="ts">
    type TaskStatus = 'running' | 'paused' | 'pending' | 'failed' | 'completed'
    type TaskType = 'recurring' | 'scheduled' | 'event-triggered' | 'monitor'

    interface Task {
        id: number
        name: string
        description?: string
        type: TaskType
        status: TaskStatus
        intervalLabel?: string
        scheduledAt?: string
        eventSource?: string
        monitorTarget?: string
        lastRunAt?: string
        nextRunAt?: string
        runCount?: number
        failCount?: number
        tags?: string[]
    }

    const tasks = ref<Task[]>([
        {
            id: 1, name: 'Library Seat Monitor', type: 'monitor', status: 'running',
            description: 'Monitors available seats in the library and notifies when a seat becomes available.',
            monitorTarget: 'Library Floor 3 Area A / 5 min',
            lastRunAt: '2024-12-14 14:30', nextRunAt: '2024-12-14 14:35',
            runCount: 576, failCount: 2, tags: ['library', 'monitor'],
        },
        {
            id: 2, name: 'Daily Report Generator', type: 'recurring', status: 'running',
            description: 'Generates a daily academic progress report and sends to email.',
            intervalLabel: 'Every day at 09:00',
            lastRunAt: '2024-12-14 09:00', nextRunAt: '2024-12-15 09:00',
            runCount: 45, failCount: 0, tags: ['report'],
        },
        {
            id: 3, name: 'Assignment Deadline Alert', type: 'event-triggered', status: 'paused',
            description: 'Triggers an alert when a new assignment deadline is detected in Blackboard.',
            eventSource: 'Blackboard: New assignment detected',
            lastRunAt: '2024-12-13 16:00', runCount: 12, failCount: 1, tags: ['alert'],
        },
        {
            id: 4, name: 'Exam Schedule Sync', type: 'scheduled', status: 'pending',
            description: 'Syncs exam schedule from Course System to calendar.',
            scheduledAt: '2024-12-20 08:00',
            runCount: 0, tags: ['exam', 'sync'],
        },
        {
            id: 5, name: 'Course Material Downloader', type: 'recurring', status: 'failed',
            description: 'Downloads new course materials from Blackboard automatically.',
            intervalLabel: 'Every hour', lastRunAt: '2024-12-14 13:00',
            runCount: 200, failCount: 5, tags: ['download'],
        },
    ])

    const search = ref('')
    const typeFilter = ref<string>('all')
    const statusFilter = ref<string>('all')

    const typeChips = [
        { value: 'all', label: 'All Types', icon: '' },
        { value: 'recurring', label: 'Recurring', icon: 'mdi-refresh' },
        { value: 'scheduled', label: 'Scheduled', icon: 'mdi-clock-outline' },
        { value: 'event-triggered', label: 'Event', icon: 'mdi-lightning-bolt' },
        { value: 'monitor', label: 'Monitor', icon: 'mdi-eye-outline' },
    ]

    const statusChips = [
        { value: 'all', label: 'All Status', color: '' },
        { value: 'running', label: 'Running', color: 'rgb(var(--v-theme-success))' },
        { value: 'paused', label: 'Paused', color: 'rgb(var(--v-theme-warning))' },
        { value: 'pending', label: 'Pending', color: 'rgb(var(--v-theme-info))' },
        { value: 'failed', label: 'Failed', color: 'rgb(var(--v-theme-error))' },
        { value: 'completed', label: 'Completed', color: '#888' },
    ]

    const filteredTasks = computed(() => tasks.value.filter(t => {
        const matchSearch = !search.value || t.name.toLowerCase().includes(search.value.toLowerCase())
        const matchType = typeFilter.value === 'all' || t.type === typeFilter.value
        const matchStatus = statusFilter.value === 'all' || t.status === statusFilter.value
        return matchSearch && matchType && matchStatus
    }))

    const countByStatus = (s: TaskStatus) => tasks.value.filter(t => t.status === s).length

    const typeIcon = (type: TaskType) => ({
        recurring: 'mdi-refresh',
        scheduled: 'mdi-clock-outline',
        'event-triggered': 'mdi-lightning-bolt',
        monitor: 'mdi-eye-outline',
    }[type])

    const typeIconColor = (type: TaskType) => ({
        recurring: 'primary',
        scheduled: 'info',
        'event-triggered': 'warning',
        monitor: 'success',
    }[type])

    const statusColor = (s: TaskStatus) => ({
        running: 'success', paused: 'warning', pending: 'info', failed: 'error', completed: undefined,
    }[s])

    const statusColorRaw = (s: TaskStatus) => ({
        paused: 'rgb(var(--v-theme-warning))',
        pending: 'rgb(var(--v-theme-info))',
        failed: 'rgb(var(--v-theme-error))',
        completed: '#888',
        running: '',
    }[s] ?? '')

    // 弹窗
    const dialogOpen = ref(false)
    const editingTask = ref<Task | null>(null)
    const deleteDialogOpen = ref(false)
    const deletingTask = ref<Task | null>(null)
    const tagInput = ref('')

    const taskTypes: { value: TaskType; icon: string; label: string; desc: string }[] = [
        { value: 'recurring', icon: 'mdi-refresh', label: 'Recurring', desc: 'Runs on a schedule' },
        { value: 'scheduled', icon: 'mdi-clock-outline', label: 'Scheduled', desc: 'Runs once at a time' },
        { value: 'event-triggered', icon: 'mdi-lightning-bolt', label: 'Event', desc: 'Triggered by events' },
        { value: 'monitor', icon: 'mdi-eye-outline', label: 'Monitor', desc: 'Watches for changes' },
    ]

    const eventSources = ['Email Inbox', 'Blackboard', 'Course System', 'Calendar', 'File System', 'Webhook']
    const pollIntervals = ['1 min', '2 min', '5 min', '15 min', '30 min', '1 hr']

    const form = ref({
        type: 'recurring' as TaskType,
        name: '',
        description: '',
        cron: '',
        intervalLabel: '',
        scheduledAt: '',
        eventSource: '',
        triggerCondition: '',
        monitorTarget: '',
        pollInterval: '5 min',
        tags: [] as string[],
    })

    const resetForm = () => {
        form.value = {
            type: 'recurring', name: '', description: '', cron: '', intervalLabel: '',
            scheduledAt: '', eventSource: '', triggerCondition: '', monitorTarget: '', pollInterval: '5 min', tags: []
        }
        tagInput.value = ''
    }

    const openCreateDialog = () => {
        editingTask.value = null
        resetForm()
        dialogOpen.value = true
    }

    const openEditDialog = (task: Task) => {
        editingTask.value = task
        form.value = {
            type: task.type, name: task.name, description: task.description ?? '',
            cron: '', intervalLabel: task.intervalLabel ?? '', scheduledAt: task.scheduledAt ?? '',
            eventSource: task.eventSource ?? '', triggerCondition: '', monitorTarget: task.monitorTarget ?? '',
            pollInterval: '5 min', tags: [...(task.tags ?? [])],
        }
        dialogOpen.value = true
    }

    const openDeleteDialog = (task: Task) => {
        deletingTask.value = task
        deleteDialogOpen.value = true
    }

    const addTag = () => {
        const t = tagInput.value.trim()
        if (t && !form.value.tags.includes(t)) form.value.tags.push(t)
        tagInput.value = ''
    }

    const saveTask = () => {
        if (editingTask.value) {
            Object.assign(editingTask.value, {
                name: form.value.name, description: form.value.description,
                type: form.value.type, intervalLabel: form.value.intervalLabel,
                scheduledAt: form.value.scheduledAt, eventSource: form.value.eventSource,
                monitorTarget: form.value.monitorTarget, tags: form.value.tags,
            })
        } else {
            tasks.value.push({
                id: Date.now(), name: form.value.name, description: form.value.description,
                type: form.value.type, status: 'pending', intervalLabel: form.value.intervalLabel,
                scheduledAt: form.value.scheduledAt, eventSource: form.value.eventSource,
                monitorTarget: form.value.monitorTarget, tags: form.value.tags, runCount: 0,
            })
        }
        dialogOpen.value = false
    }

    const confirmDelete = () => {
        if (deletingTask.value) {
            tasks.value = tasks.value.filter(t => t.id !== deletingTask.value!.id)
        }
        deleteDialogOpen.value = false
    }

    const togglePause = (task: Task) => {
        task.status = task.status === 'running' ? 'paused' : 'running'
    }

    const toggleTask = (task: Task) => {
        if (task.status === 'paused' || task.status === 'failed') {
            task.status = 'running'
        } else {
            task.status = 'paused'
        }
    }
</script>

<style scoped>
    .status-dot {
        display: inline-block;
        width: 6px;
        height: 6px;
        border-radius: 50%;
        flex-shrink: 0;
    }

    .dot-running {
        background: rgb(var(--v-theme-success));
        animation: pulse 2s infinite;
    }

    @keyframes pulse {

        0%,
        100% {
            opacity: 1;
            transform: scale(1);
        }

        50% {
            opacity: 0.5;
            transform: scale(1.4);
        }
    }

    /* 筛选芯片 */
    .filter-chip {
        display: inline-flex;
        align-items: center;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: 500;
        border-radius: 6px;
        border: none;
        cursor: pointer;
        transition: background 0.15s, color 0.15s;
        color: rgba(var(--v-theme-on-surface), 0.6);
        background: transparent;
    }

    .filter-chip:hover {
        background: rgba(var(--v-theme-surface-variant), 0.5);
        color: rgba(var(--v-theme-on-surface), 1);
    }

    .filter-chip.active {
        background: rgba(var(--v-theme-primary), 0.15);
        color: rgb(var(--v-theme-primary));
    }

    /* 元数据项 */
    .meta-item {
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }

    /* 任务卡片 */
    .task-card {
        border-radius: 12px;
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        padding: 16px;
        transition: all 0.2s;
    }

    .task-card--running {
        border-color: rgba(var(--v-theme-success), 0.2);
        background: rgba(var(--v-theme-success), 0.03);
    }

    .task-card--failed {
        border-color: rgba(var(--v-theme-error), 0.2);
        background: rgba(var(--v-theme-error), 0.03);
    }

    .task-card--paused {
        border-color: rgba(var(--v-theme-warning), 0.15);
    }

    .task-card--completed {
        opacity: 0.6;
    }

    /* 类型图标容器 */
    .task-type-icon {
        width: 36px;
        height: 36px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(var(--v-theme-surface-variant), 0.5);
    }

    .task-type-icon--running {
        background: rgba(var(--v-theme-success), 0.1);
    }

    .task-type-icon--failed {
        background: rgba(var(--v-theme-error), 0.1);
    }

    .task-type-icon--paused {
        background: rgba(var(--v-theme-warning), 0.1);
    }

    /* 类型选择卡片 */
    .type-option {
        display: flex;
        align-items: center;
        gap: 10px;
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        border-radius: 8px;
        padding: 12px;
        cursor: pointer;
        transition: border-color 0.15s, background 0.15s;
    }

    .type-option:hover {
        border-color: rgba(var(--v-theme-on-surface), 0.3);
    }

    .type-option--active {
        border-color: rgba(var(--v-theme-primary), 0.5);
        background: rgba(var(--v-theme-primary), 0.1);
    }

    /* 类型配置块 */
    .type-config-block {
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        border-radius: 8px;
        background: rgba(var(--v-theme-surface), 0.5);
        padding: 12px;
    }

    /* 标签输入框 */
    .tag-input {
        height: 28px;
        width: 96px;
        font-size: 12px;
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        border-radius: 6px;
        padding: 0 8px;
        background: transparent;
        color: inherit;
        outline: none;
    }

    .tag-input:focus {
        border-color: rgb(var(--v-theme-primary));
    }

    /* 搜索框左侧图标 */
    .search-input :deep(.v-field__input) {
        padding-inline-start: 32px !important;
        font-size: 12px;
        min-height: 32px !important;
        padding-top: 4px !important;
        padding-bottom: 4px !important;
    }
</style>
