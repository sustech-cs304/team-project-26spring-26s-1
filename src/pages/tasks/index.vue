<template>
    <v-container fluid class="d-flex flex-column pa-0" style="height:100%;overflow:hidden;">

        <!-- ── 统计栏 ── -->
        <v-sheet class="px-5 py-2 border-b flex-shrink-0" color="transparent">
            <div class="d-flex align-center justify-space-between">
                <div class="d-flex align-center ga-3">
                    <div class="d-flex align-center ga-1">
                        <span class="text-subtitle-2 font-weight-bold" style="font-variant-numeric:tabular-nums;">{{
                            tasks.length }}</span>
                        <span class="text-caption text-medium-emphasis">Total</span>
                    </div>
                    <v-divider vertical style="height:14px;" />
                    <div class="d-flex align-center ga-1">
                        <span class="stat-dot dot-running" />
                        <span class="text-subtitle-2 font-weight-bold text-success">{{ countByStatus('running')
                        }}</span>
                        <span class="text-caption text-medium-emphasis">Running</span>
                    </div>
                    <v-divider vertical style="height:14px;" />
                    <div class="d-flex align-center ga-1">
                        <span class="stat-dot" style="background:rgb(var(--v-theme-warning))" />
                        <span class="text-subtitle-2 font-weight-bold text-warning">{{ countByStatus('paused') }}</span>
                        <span class="text-caption text-medium-emphasis">Paused</span>
                    </div>
                    <v-divider vertical style="height:14px;" />
                    <div class="d-flex align-center ga-1">
                        <span class="stat-dot" style="background:rgb(var(--v-theme-error))" />
                        <span class="text-subtitle-2 font-weight-bold text-error">{{ countByStatus('failed') }}</span>
                        <span class="text-caption text-medium-emphasis">Failed</span>
                    </div>
                </div>
                <v-btn size="small" color="primary" @click="openCreate">
                    <v-icon size="14" class="mr-1">mdi-plus</v-icon>New Task
                </v-btn>
            </div>
        </v-sheet>

        <!-- ── 主体分栏 ── -->
        <div class="d-flex flex-grow-1" style="overflow:hidden;min-height:0;">

            <!-- ══ 左栏：任务列表 ══ -->
            <div class="d-flex flex-column border-e flex-shrink-0" style="width:360px;overflow:hidden;">

                <!-- 搜索 & 筛选 -->
                <v-sheet class="px-3 pt-3 pb-2 flex-shrink-0" color="transparent">
                    <v-text-field v-model="search" density="compact" variant="outlined" placeholder="Search tasks..."
                        hide-details prepend-inner-icon="mdi-magnify" style="font-size:12px;" class="mb-2" />
                    <div class="d-flex flex-wrap ga-1 mb-1">
                        <v-chip v-for="c in typeChips" :key="c.value" :prepend-icon="c.icon || undefined" size="x-small"
                            :variant="typeFilter === c.value ? 'tonal' : 'text'"
                            :color="typeFilter === c.value ? 'primary' : undefined" @click="typeFilter = c.value">{{
                                c.label }}</v-chip>
                    </div>
                    <div class="d-flex flex-wrap ga-1">
                        <v-chip v-for="c in statusChips" :key="c.value" size="x-small"
                            :variant="statusFilter === c.value ? 'tonal' : 'text'"
                            :color="statusFilter === c.value ? 'primary' : undefined" @click="statusFilter = c.value">
                            <template v-if="c.color" #prepend>
                                <span class="stat-dot mr-1" :class="{ 'dot-running': c.value === 'running' }"
                                    :style="c.value !== 'running' ? { background: c.color } : {}" />
                            </template>
                            {{ c.label }}
                        </v-chip>
                    </div>
                </v-sheet>

                <v-divider />

                <!-- 列表 -->
                <div class="flex-grow-1 overflow-y-auto">
                    <div v-if="filteredTasks.length === 0" class="d-flex flex-column align-center justify-center py-12">
                        <v-icon size="28" class="text-medium-emphasis mb-2" style="opacity:.4;">mdi-list-status</v-icon>
                        <span class="text-caption text-medium-emphasis">No tasks found</span>
                    </div>
                    <div v-else>
                        <div v-for="task in filteredTasks" :key="task.id"
                            class="task-list-item px-3 py-2 cursor-pointer"
                            :class="{ 'task-list-item--active': selectedTaskId === task.id }"
                            @click="selectedTaskId = task.id">
                            <div class="d-flex align-center ga-2">
                                <v-avatar :color="typeIconColor(task.type)" size="28" rounded="lg">
                                    <v-icon size="14" color="white">{{ typeIcon(task.type) }}</v-icon>
                                </v-avatar>
                                <div class="flex-grow-1 min-width-0">
                                    <div class="d-flex align-center ga-1 flex-wrap">
                                        <span class="text-body-2 font-weight-medium text-truncate"
                                            style="max-width:160px;">{{ task.name
                                            }}</span>
                                        <v-chip :color="statusColor(task.status)" variant="outlined" size="x-small"
                                            density="compact" style="font-size:9px;height:16px;">{{ task.status
                                            }}</v-chip>
                                    </div>
                                    <div v-if="task.description" class="text-caption text-medium-emphasis text-truncate"
                                        style="font-size:11px;max-width:220px;">
                                        {{ task.description }}
                                    </div>
                                    <template v-if="task.status === 'running' && task.steps.length">
                                        <div class="d-flex align-center ga-1 mt-1">
                                            <v-progress-linear :model-value="runningProgress(task)" color="primary"
                                                height="3" rounded style="max-width:120px;flex-shrink:0;" />
                                            <span class="text-caption text-medium-emphasis" style="font-size:10px;">
                                                Step {{ runningStepIndex(task) }}/{{ task.steps.length }}
                                            </span>
                                        </div>
                                    </template>
                                    <div v-if="task.lastRunAt" class="d-flex align-center ga-1 mt-1">
                                        <v-icon size="10" class="text-disabled">mdi-history</v-icon>
                                        <span class="text-caption text-disabled" style="font-size:10px;">{{
                                            task.lastRunAt }}</span>
                                    </div>
                                </div>
                                <v-switch :model-value="task.status !== 'paused' && task.status !== 'failed'"
                                    density="compact" hide-details color="success"
                                    style="transform:scale(0.7);transform-origin:right center;flex-shrink:0;"
                                    @change="toggleTask(task)" @click.stop />
                            </div>
                            <v-divider class="mt-2" />
                        </div>
                    </div>
                </div>
            </div>

            <!-- ══ 右栏：详情面板 ══ -->
            <div class="flex-grow-1 d-flex flex-column" style="overflow:hidden;min-width:0;">

                <!-- 空状态 -->
                <div v-if="!selectedTask" class="flex-grow-1 d-flex flex-column align-center justify-center">
                    <v-icon size="48" class="text-medium-emphasis mb-3" style="opacity:.3;">mdi-robot-outline</v-icon>
                    <span class="text-body-2 text-medium-emphasis">选择一个任务查看详情</span>
                    <span class="text-caption text-disabled mt-1">Select a task from the list</span>
                </div>

                <!-- 详情内容 -->
                <template v-else>
                    <!-- 详情头部 -->
                    <v-sheet class="px-5 py-4 border-b flex-shrink-0" color="transparent">
                        <div class="d-flex align-start ga-3">
                            <v-avatar :color="typeIconColor(selectedTask.type)" size="40" rounded="lg">
                                <v-icon size="20" color="white">{{ typeIcon(selectedTask.type) }}</v-icon>
                            </v-avatar>
                            <div class="flex-grow-1 min-width-0">
                                <div class="text-h6 font-weight-bold">{{ selectedTask.name }}</div>
                                <div v-if="selectedTask.description" class="text-caption text-medium-emphasis mt-1">
                                    {{ selectedTask.description }}
                                </div>
                                <div class="d-flex flex-wrap align-center ga-2 mt-2">
                                    <v-chip :color="statusColor(selectedTask.status)" variant="tonal" size="x-small">
                                        <template #prepend>
                                            <span class="stat-dot mr-1"
                                                :class="{ 'dot-running': selectedTask.status === 'running' }"
                                                :style="selectedTask.status !== 'running' ? { background: `rgb(var(--v-theme-${statusColor(selectedTask.status)}))` } : {}" />
                                        </template>
                                        {{ selectedTask.status }}
                                    </v-chip>
                                    <v-chip variant="tonal" :color="typeIconColor(selectedTask.type)" size="x-small">
                                        {{ selectedTask.type }}
                                    </v-chip>
                                    <v-chip v-if="selectedTask.successRate != null" variant="tonal" color="success"
                                        size="x-small">
                                        <v-icon start size="10">mdi-check-circle</v-icon>
                                        {{ selectedTask.successRate }}% success
                                    </v-chip>
                                    <v-chip v-if="selectedTask.averageDuration" variant="tonal" color="info"
                                        size="x-small">
                                        <v-icon start size="10">mdi-timer-outline</v-icon>
                                        avg {{ formatDuration(selectedTask.averageDuration) }}
                                    </v-chip>
                                </div>
                                <template v-if="selectedTask.status === 'running' && selectedTask.steps.length">
                                    <div class="d-flex align-center ga-2 mt-2">
                                        <v-progress-linear :model-value="runningProgress(selectedTask)" color="primary"
                                            height="4" rounded style="max-width:200px;" />
                                        <span class="text-caption text-medium-emphasis" style="font-size:11px;">
                                            Step {{ runningStepIndex(selectedTask) }}/{{ selectedTask.steps.length }}
                                        </span>
                                    </div>
                                </template>
                            </div>
                            <div class="d-flex align-center ga-2 flex-shrink-0">
                                <v-btn size="small" color="primary" variant="flat" :loading="!!selectedTask.currentRun"
                                    @click="runNow(selectedTask)">
                                    <v-icon size="14" class="mr-1">mdi-play</v-icon>Run Now
                                </v-btn>
                                <v-btn size="small" variant="outlined"
                                    :icon="selectedTask.status === 'running' ? 'mdi-pause' : 'mdi-play'"
                                    @click="togglePause(selectedTask)" />
                                <v-btn size="small" variant="outlined" icon="mdi-pencil"
                                    @click="openEdit(selectedTask)" />
                                <v-btn size="small" variant="outlined" color="error" icon="mdi-delete"
                                    @click="openDelete(selectedTask)" />
                            </div>
                        </div>
                    </v-sheet>

                    <!-- Tabs -->
                    <v-tabs v-model="detailTab" density="compact" class="border-b flex-shrink-0">
                        <v-tab value="steps" class="text-caption">
                            <v-icon size="14" class="mr-1">mdi-format-list-numbered</v-icon>Steps
                        </v-tab>
                        <v-tab value="runlogs" class="text-caption">
                            <v-icon size="14" class="mr-1">mdi-history</v-icon>Run Logs
                            <v-chip v-if="selectedTask.runLogs.length" size="x-small" class="ml-1" variant="tonal">
                                {{ selectedTask.runLogs.length }}
                            </v-chip>
                        </v-tab>
                        <v-tab value="config" class="text-caption">
                            <v-icon size="14" class="mr-1">mdi-cog-outline</v-icon>Config
                        </v-tab>
                    </v-tabs>

                    <!-- Tab 内容 -->
                    <div class="flex-grow-1 overflow-y-auto">
                        <v-tabs-window v-model="detailTab">

                            <!-- ── Tab: Steps ── -->
                            <v-tabs-window-item value="steps">
                                <div class="pa-5">
                                    <div v-if="!selectedTask.steps.length"
                                        class="d-flex flex-column align-center py-12">
                                        <v-icon size="32" class="text-medium-emphasis mb-2"
                                            style="opacity:.4;">mdi-playlist-plus</v-icon>
                                        <span class="text-caption text-medium-emphasis">暂无步骤定义</span>
                                    </div>
                                    <div v-else class="d-flex flex-column">
                                        <div v-for="(step, idx) in selectedTask.steps" :key="step.id"
                                            class="d-flex ga-3">
                                            <!-- 左侧节点 + 连接线 -->
                                            <div class="d-flex flex-column align-center flex-shrink-0"
                                                style="width:32px;">
                                                <v-icon :color="STEP_STATUS_COLOR[step.status]" :size="20"
                                                    :class="{ 'spin-anim': step.status === 'running' }">{{
                                                        STEP_STATUS_ICON[step.status]
                                                    }}</v-icon>
                                                <div v-if="idx < selectedTask.steps.length - 1" class="mt-1" :style="{
                                                    width: '2px',
                                                    flexGrow: 1,
                                                    minHeight: '24px',
                                                    background: step.status === 'completed'
                                                        ? 'rgb(var(--v-theme-success))'
                                                        : 'rgba(var(--v-border-color), var(--v-border-opacity))',
                                                    borderLeft: step.status !== 'completed' ? '2px dashed rgba(var(--v-border-color), var(--v-border-opacity))' : 'none',
                                                }" />
                                            </div>
                                            <!-- 右侧内容 -->
                                            <div class="flex-grow-1 pb-4 min-width-0">
                                                <div class="d-flex align-center ga-2 flex-wrap">
                                                    <span class="text-caption text-medium-emphasis font-weight-bold"
                                                        style="font-size:10px;">
                                                        Step {{ step.index }}
                                                    </span>
                                                    <span class="text-body-2 font-weight-medium">{{ step.name }}</span>
                                                    <v-chip :color="STEP_STATUS_COLOR[step.status]" variant="tonal"
                                                        size="x-small" density="compact"
                                                        style="font-size:9px;height:16px;">{{ step.status }}</v-chip>
                                                    <span v-if="step.duration" class="text-caption text-medium-emphasis"
                                                        style="font-size:10px;">
                                                        {{ formatDuration(step.duration) }}
                                                    </span>
                                                    <span v-else-if="step.status === 'running'"
                                                        class="text-caption text-primary" style="font-size:10px;">
                                                        运行中...
                                                    </span>
                                                </div>
                                                <div v-if="step.description"
                                                    class="text-caption text-medium-emphasis mt-1">
                                                    {{ step.description }}
                                                </div>
                                                <div v-if="step.toolName || step.output || step.input || step.errorMessage"
                                                    class="mt-1">
                                                    <v-expansion-panels variant="accordion" flat>
                                                        <v-expansion-panel bg-color="transparent" elevation="0"
                                                            style="border:1px solid rgba(var(--v-border-color),var(--v-border-opacity));border-radius:8px;">
                                                            <v-expansion-panel-title class="pa-2"
                                                                style="min-height:28px;">
                                                                <span class="text-caption text-medium-emphasis"
                                                                    style="font-size:10px;">
                                                                    <v-icon size="11" class="mr-1">mdi-tools</v-icon>
                                                                    {{ step.toolName ?? 'details' }}
                                                                </span>
                                                            </v-expansion-panel-title>
                                                            <v-expansion-panel-text class="pa-0">
                                                                <div class="px-3 pb-3 d-flex flex-column ga-2">
                                                                    <div v-if="step.input">
                                                                        <div class="text-caption text-medium-emphasis mb-1"
                                                                            style="font-size:10px;text-transform:uppercase;letter-spacing:.05em;">
                                                                            Input</div>
                                                                        <v-sheet rounded="md" color="surface-variant"
                                                                            class="pa-2"
                                                                            style="font-family:monospace;font-size:11px;white-space:pre-wrap;word-break:break-all;">{{
                                                                                tryFormat(step.input) }}</v-sheet>
                                                                    </div>
                                                                    <div v-if="step.output">
                                                                        <div class="text-caption text-medium-emphasis mb-1"
                                                                            style="font-size:10px;text-transform:uppercase;letter-spacing:.05em;">
                                                                            Output</div>
                                                                        <v-sheet rounded="md" color="surface-variant"
                                                                            class="pa-2"
                                                                            style="font-family:monospace;font-size:11px;white-space:pre-wrap;word-break:break-all;">{{
                                                                                tryFormat(step.output) }}</v-sheet>
                                                                    </div>
                                                                    <div v-if="step.errorMessage">
                                                                        <div class="text-caption text-error mb-1"
                                                                            style="font-size:10px;text-transform:uppercase;letter-spacing:.05em;">
                                                                            Error</div>
                                                                        <v-alert type="error" variant="tonal"
                                                                            density="compact" class="text-caption">
                                                                            {{ step.errorMessage }}
                                                                        </v-alert>
                                                                    </div>
                                                                </div>
                                                            </v-expansion-panel-text>
                                                        </v-expansion-panel>
                                                    </v-expansion-panels>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </v-tabs-window-item>

                            <!-- ── Tab: Run Logs ── -->
                            <v-tabs-window-item value="runlogs">
                                <div class="pa-4">
                                    <div v-if="!selectedTask.runLogs.length"
                                        class="d-flex flex-column align-center py-12">
                                        <v-icon size="32" class="text-medium-emphasis mb-2"
                                            style="opacity:.4;">mdi-history</v-icon>
                                        <span class="text-caption text-medium-emphasis">暂无执行记录</span>
                                    </div>
                                    <div v-else class="d-flex flex-column ga-2">
                                        <v-expansion-panels v-model="expandedLog" variant="accordion">
                                            <v-expansion-panel v-for="log in selectedTask.runLogs" :key="log.id"
                                                :value="log.id" rounded="lg"
                                                style="border:1px solid rgba(var(--v-border-color),var(--v-border-opacity));"
                                                elevation="0">
                                                <v-expansion-panel-title class="px-3 py-2" style="min-height:44px;">
                                                    <div class="d-flex align-center ga-2 flex-wrap w-100">
                                                        <v-icon :color="RUN_STATUS_COLOR[log.status]"
                                                            :class="{ 'spin-anim': log.status === 'running' }"
                                                            size="16">{{
                                                                RUN_STATUS_ICON[log.status] }}</v-icon>
                                                        <span class="text-body-2 font-weight-bold"
                                                            style="font-variant-numeric:tabular-nums;">#{{ log.runNumber
                                                            }}</span>
                                                        <v-chip size="x-small" variant="tonal"
                                                            :color="RUN_STATUS_COLOR[log.status]" density="compact"
                                                            style="font-size:9px;height:16px;">
                                                            {{ log.status }}
                                                        </v-chip>
                                                        <v-chip size="x-small" variant="outlined" density="compact"
                                                            style="font-size:9px;height:16px;">
                                                            <v-icon start size="10">{{ log.triggerType === 'manual' ?
                                                                'mdi-hand-pointing-right' : log.triggerType === 'event'
                                                                    ?
                                                                    'mdi-lightning-bolt' : 'mdi-clock-outline' }}</v-icon>
                                                            {{ log.triggerType }}
                                                        </v-chip>
                                                        <span class="text-caption text-medium-emphasis"
                                                            style="font-size:10px;">{{
                                                                log.startedAt }}</span>
                                                        <v-spacer />
                                                        <span v-if="log.duration"
                                                            class="text-caption text-medium-emphasis"
                                                            style="font-size:10px;">{{ formatDuration(log.duration)
                                                            }}</span>
                                                        <v-chip size="x-small" variant="tonal" density="compact"
                                                            style="font-size:9px;height:16px;">
                                                            {{ log.stepsCompleted }}/{{ log.stepsTotal }} steps
                                                        </v-chip>
                                                    </div>
                                                </v-expansion-panel-title>
                                                <v-expansion-panel-text>
                                                    <div class="pt-1 pb-2">
                                                        <div v-if="log.summary"
                                                            class="text-caption text-medium-emphasis mb-2">
                                                            <v-icon size="12"
                                                                class="mr-1">mdi-information-outline</v-icon>{{
                                                                    log.summary }}
                                                        </div>
                                                        <div v-if="log.errorMessage"
                                                            class="text-caption text-error mb-2">
                                                            <v-icon size="12" class="mr-1">mdi-alert-circle</v-icon>{{
                                                                log.errorMessage }}
                                                        </div>
                                                        <div v-if="log.steps && log.steps.length">
                                                            <v-divider class="mb-2" />
                                                            <div v-for="s in log.steps" :key="s.id"
                                                                class="d-flex align-center ga-2 mb-1">
                                                                <v-icon :color="STEP_STATUS_COLOR[s.status]"
                                                                    size="13">{{
                                                                        STEP_STATUS_ICON[s.status] }}</v-icon>
                                                                <span class="text-caption">{{ s.name }}</span>
                                                                <span v-if="s.duration"
                                                                    class="text-caption text-medium-emphasis ml-auto"
                                                                    style="font-size:10px;">{{
                                                                        formatDuration(s.duration) }}</span>
                                                            </div>
                                                        </div>
                                                        <div v-else class="text-caption text-disabled"
                                                            style="font-size:10px;">
                                                            <v-icon size="10"
                                                                class="mr-1">mdi-information-outline</v-icon>无步骤快照
                                                        </div>
                                                    </div>
                                                </v-expansion-panel-text>
                                            </v-expansion-panel>
                                        </v-expansion-panels>
                                    </div>
                                </div>
                            </v-tabs-window-item>

                            <!-- ── Tab: Config ── -->
                            <v-tabs-window-item value="config">
                                <div class="pa-5">
                                    <v-list density="compact" lines="two">
                                        <v-list-item
                                            v-if="selectedTask.type === 'recurring' && selectedTask.intervalLabel">
                                            <template #prepend><v-icon size="16"
                                                    class="text-medium-emphasis mr-2">mdi-refresh</v-icon></template>
                                            <v-list-item-title
                                                class="text-caption font-weight-bold">Schedule</v-list-item-title>
                                            <v-list-item-subtitle class="text-caption">{{ selectedTask.intervalLabel
                                            }}</v-list-item-subtitle>
                                        </v-list-item>
                                        <v-list-item
                                            v-if="selectedTask.type === 'scheduled' && selectedTask.scheduledAt">
                                            <template #prepend><v-icon size="16"
                                                    class="text-medium-emphasis mr-2">mdi-clock-outline</v-icon></template>
                                            <v-list-item-title class="text-caption font-weight-bold">Scheduled
                                                At</v-list-item-title>
                                            <v-list-item-subtitle class="text-caption">{{ selectedTask.scheduledAt
                                            }}</v-list-item-subtitle>
                                        </v-list-item>
                                        <v-list-item v-if="selectedTask.eventSource">
                                            <template #prepend><v-icon size="16"
                                                    class="text-medium-emphasis mr-2">mdi-lightning-bolt</v-icon></template>
                                            <v-list-item-title class="text-caption font-weight-bold">Event
                                                Source</v-list-item-title>
                                            <v-list-item-subtitle class="text-caption">{{ selectedTask.eventSource
                                            }}</v-list-item-subtitle>
                                        </v-list-item>
                                        <v-list-item v-if="selectedTask.triggerCondition">
                                            <template #prepend><v-icon size="16"
                                                    class="text-medium-emphasis mr-2">mdi-filter-outline</v-icon></template>
                                            <v-list-item-title class="text-caption font-weight-bold">Trigger
                                                Condition</v-list-item-title>
                                            <v-list-item-subtitle class="text-caption">{{ selectedTask.triggerCondition
                                            }}</v-list-item-subtitle>
                                        </v-list-item>
                                        <v-list-item v-if="selectedTask.monitorTarget">
                                            <template #prepend><v-icon size="16"
                                                    class="text-medium-emphasis mr-2">mdi-eye-outline</v-icon></template>
                                            <v-list-item-title class="text-caption font-weight-bold">Monitor
                                                Target</v-list-item-title>
                                            <v-list-item-subtitle class="text-caption">{{ selectedTask.monitorTarget
                                            }}</v-list-item-subtitle>
                                        </v-list-item>
                                        <v-list-item>
                                            <template #prepend><v-icon size="16"
                                                    class="text-medium-emphasis mr-2">mdi-calendar-outline</v-icon></template>
                                            <v-list-item-title class="text-caption font-weight-bold">Created
                                                At</v-list-item-title>
                                            <v-list-item-subtitle class="text-caption">{{ selectedTask.createdAt ?? '—'
                                            }}</v-list-item-subtitle>
                                        </v-list-item>
                                        <v-list-item>
                                            <template #prepend><v-icon size="16"
                                                    class="text-medium-emphasis mr-2">mdi-pound</v-icon></template>
                                            <v-list-item-title class="text-caption font-weight-bold">Run
                                                Statistics</v-list-item-title>
                                            <v-list-item-subtitle class="text-caption">
                                                {{ selectedTask.runCount ?? 0 }} total runs · {{ selectedTask.failCount
                                                    ?? 0 }} failures
                                            </v-list-item-subtitle>
                                        </v-list-item>
                                        <v-list-item v-if="selectedTask.tags && selectedTask.tags.length">
                                            <template #prepend><v-icon size="16"
                                                    class="text-medium-emphasis mr-2">mdi-tag-outline</v-icon></template>
                                            <v-list-item-title
                                                class="text-caption font-weight-bold">Tags</v-list-item-title>
                                            <template #append>
                                                <div class="d-flex flex-wrap ga-1">
                                                    <v-chip v-for="tag in selectedTask.tags" :key="tag" variant="tonal"
                                                        size="x-small" density="compact"
                                                        style="font-size:9px;height:16px;">{{ tag }}</v-chip>
                                                </div>
                                            </template>
                                        </v-list-item>
                                    </v-list>
                                </div>
                            </v-tabs-window-item>

                        </v-tabs-window>
                    </div>
                </template>
            </div>
        </div>

        <!-- ══ 弹窗 ══ -->
        <TaskEditDialog v-model="dialogOpen" :task="editingTask" @submit="saveTask" />
        <TaskLogDialog v-model="logDialogOpen" :task="logTask" />

        <v-dialog v-model="deleteDialogOpen" max-width="360">
            <v-card rounded="lg">
                <v-card-title class="d-flex align-center ga-2 px-4 pt-4 pb-2">
                    <v-icon size="16" color="error">mdi-alert-triangle</v-icon>
                    <span class="text-body-2 font-weight-bold">Delete Task</span>
                </v-card-title>
                <v-card-text class="text-body-2 px-4 py-2">
                    Are you sure you want to delete <strong>{{ deletingTask?.name }}</strong>? This cannot be undone.
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
    import TaskEditDialog from '@/components/tasks/TaskEditDialog.vue'
    import TaskLogDialog from '@/components/tasks/TaskLogDialog.vue'
    import { buildDefaultTasks } from '@/api/tasks'
    import type { Task, TaskForm, TaskStatus, TaskStep, TaskRunLog } from '@/utils/tasks'
    import {
        formToTaskPatch,
        typeIcon, typeIconColor, statusColor,
        STEP_STATUS_COLOR, STEP_STATUS_ICON,
        RUN_STATUS_COLOR, RUN_STATUS_ICON,
        formatDuration,
    } from '@/utils/tasks'

    const tasks = ref<Task[]>(buildDefaultTasks())

    // ── 筛选 ──
    const search = ref('')
    const typeFilter = ref('all')
    const statusFilter = ref('all')

    const typeChips = [
        { value: 'all', label: 'All', icon: '' },
        { value: 'recurring', label: 'Recurring', icon: 'mdi-refresh' },
        { value: 'scheduled', label: 'Scheduled', icon: 'mdi-clock-outline' },
        { value: 'event-triggered', label: 'Event', icon: 'mdi-lightning-bolt' },
        { value: 'monitor', label: 'Monitor', icon: 'mdi-eye-outline' },
    ]
    const statusChips = [
        { value: 'all', label: 'All', color: '' },
        { value: 'running', label: 'Running', color: 'rgb(var(--v-theme-success))' },
        { value: 'paused', label: 'Paused', color: 'rgb(var(--v-theme-warning))' },
        { value: 'pending', label: 'Pending', color: 'rgb(var(--v-theme-info))' },
        { value: 'failed', label: 'Failed', color: 'rgb(var(--v-theme-error))' },
        { value: 'completed', label: 'Done', color: '#888' },
    ]

    const filteredTasks = computed(() => tasks.value.filter(t => {
        const q = search.value.toLowerCase()
        return (!q || t.name.toLowerCase().includes(q) || (t.description ?? '').toLowerCase().includes(q))
            && (typeFilter.value === 'all' || t.type === typeFilter.value)
            && (statusFilter.value === 'all' || t.status === statusFilter.value)
    }))

    const countByStatus = (s: TaskStatus) => tasks.value.filter(t => t.status === s).length

    // ── 选中任务 ──
    const selectedTaskId = ref<number | null>(null)
    const selectedTask = computed(() => tasks.value.find(t => t.id === selectedTaskId.value) ?? null)
    const detailTab = ref('steps')
    const expandedLog = ref<string | null>(null)

    watch(selectedTaskId, () => {
        detailTab.value = 'steps'
        expandedLog.value = null
    })

    // ── 进度计算 ──
    function runningStepIndex (task: Task): number {
        const runningIdx = task.steps.findIndex(s => s.status === 'running')
        if (runningIdx >= 0) return runningIdx + 1
        const completedCount = task.steps.filter(s => s.status === 'completed').length
        return Math.min(completedCount + 1, task.steps.length)
    }

    function runningProgress (task: Task): number {
        if (!task.steps.length) return 0
        const completed = task.steps.filter(s => s.status === 'completed').length
        return Math.round((completed / task.steps.length) * 100)
    }

    // ── JSON 格式化 ──
    function tryFormat (json: string): string {
        try { return JSON.stringify(JSON.parse(json), null, 2) }
        catch { return json }
    }

    // ── Run Now ──
    let runIdCounter = 10000
    function runNow (task: Task) {
        if (task.currentRun) return
        const runNumber = (task.runCount ?? 0) + 1
        const runId = `run-${++runIdCounter}`
        const stepsSnapshot: TaskStep[] = task.steps.map(s => ({
            ...s, status: 'pending' as const, duration: undefined,
            startedAt: undefined, completedAt: undefined, output: undefined, errorMessage: undefined,
        }))
        const nowStr = () => new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-')
        const newLog: TaskRunLog = {
            id: runId, runNumber,
            status: 'running',
            startedAt: nowStr(),
            stepsCompleted: 0, stepsTotal: task.steps.length,
            triggerType: 'manual',
            steps: stepsSnapshot,
        }

        task.runLogs.unshift(newLog)
        task.currentRun = newLog
        task.status = 'running'
        task.runCount = runNumber

        task.steps.forEach(s => {
            s.status = 'pending'; s.duration = undefined
            s.startedAt = undefined; s.completedAt = undefined
        })

        const startTime = Date.now()
        let stepIdx = 0
        const advance = () => {
            if (stepIdx >= task.steps.length) {
                newLog.status = 'success'
                newLog.completedAt = nowStr()
                newLog.duration = Date.now() - startTime
                newLog.stepsCompleted = task.steps.length
                newLog.summary = `All ${task.steps.length} steps completed successfully`
                task.lastRunDuration = newLog.duration
                task.lastRunAt = newLog.startedAt
                task.currentRun = undefined
                return
            }
            const step = task.steps[stepIdx]!
            step.status = 'running'
            step.startedAt = nowStr()
            const delay = 800 + Math.floor(Math.random() * 700)
            setTimeout(() => {
                step.status = 'completed'
                step.duration = delay
                step.completedAt = nowStr()
                newLog.stepsCompleted = stepIdx + 1
                const snap = stepsSnapshot[stepIdx]
                if (snap) { snap.status = 'completed'; snap.duration = delay }
                stepIdx++
                advance()
            }, delay)
        }
        advance()
    }

    // ── 弹窗 ──
    const dialogOpen = ref(false)
    const editingTask = ref<Task | null>(null)
    const deleteDialogOpen = ref(false)
    const deletingTask = ref<Task | null>(null)
    const logDialogOpen = ref(false)
    const logTask = ref<Task | null>(null)

    const openCreate = () => { editingTask.value = null; dialogOpen.value = true }
    const openEdit = (t: Task) => { editingTask.value = t; dialogOpen.value = true }
    const openDelete = (t: Task) => { deletingTask.value = t; deleteDialogOpen.value = true }

    const saveTask = (form: TaskForm) => {
        if (editingTask.value) {
            Object.assign(editingTask.value, formToTaskPatch(form))
        } else {
            const newTask = {
                id: Date.now(), status: 'pending' as const, runCount: 0,
                createdAt: new Date().toISOString().slice(0, 10),
                steps: [], runLogs: [],
                ...formToTaskPatch(form),
            } as Task
            tasks.value.push(newTask)
        }
    }

    const confirmDelete = () => {
        if (deletingTask.value) {
            if (selectedTaskId.value === deletingTask.value.id) selectedTaskId.value = null
            tasks.value = tasks.value.filter(t => t.id !== deletingTask.value!.id)
        }
        deleteDialogOpen.value = false
    }

    const togglePause = (t: Task) => { t.status = t.status === 'running' ? 'paused' : 'running' }
    const toggleTask = (t: Task) => {
        t.status = (t.status === 'paused' || t.status === 'failed') ? 'running' : 'paused'
    }
</script>

<style scoped>
    .stat-dot {
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

    .spin-anim {
        animation: spin 1.2s linear infinite;
    }

    @keyframes spin {
        from {
            transform: rotate(0deg);
        }

        to {
            transform: rotate(360deg);
        }
    }

    .task-list-item {
        border-left: 2px solid transparent;
        transition: background-color 0.15s, border-color 0.15s;
    }

    .task-list-item:hover {
        background-color: rgba(var(--v-theme-on-surface), 0.04);
    }

    .task-list-item--active {
        border-left-color: rgb(var(--v-theme-primary));
        background-color: rgba(var(--v-theme-primary), 0.06);
    }

    .cursor-pointer {
        cursor: pointer;
    }
</style>
