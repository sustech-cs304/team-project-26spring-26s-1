<template>
    <v-card rounded="lg" elevation="0" border min-height="680">
        <template v-if="task">
            <v-card-item class="px-5 pt-4 pb-2">
                <div class="d-flex align-start justify-space-between ga-3 flex-wrap">
                    <div class="d-flex align-center ga-2 flex-wrap">
                        <div class="text-body-1 font-weight-bold">{{ task.name }}</div>
                        <v-chip :color="TASK_STATUS_COLOR[task.status]" size="small" variant="tonal">
                            <v-icon start size="14">{{ TASK_STATUS_ICON[task.status] }}</v-icon>
                            {{ TASK_STATUS_LABEL[task.status] }}
                        </v-chip>
                    </div>

                    <div class="d-flex align-center ga-2">
                        <v-btn :color="task.status === 'running' ? undefined : 'primary'" rounded="lg" size="small"
                            :variant="task.status === 'running' ? 'tonal' : 'elevated'"
                            :prepend-icon="task.status === 'running' ? 'mdi-progress-clock' : 'mdi-play'"
                            :loading="triggering" :disabled="task.status === 'running'" @click="emit('trigger')">
                            {{ task.status === 'running' ? '运行中' : '立即运行' }}
                        </v-btn>
                        <v-menu>
                            <template #activator="{ props }">
                                <v-btn v-bind="props" icon="mdi-dots-horizontal" variant="text" rounded="lg"
                                    size="small" width="40" height="32" min-width="40" />
                            </template>
                            <v-list rounded="lg" density="compact" class="task-menu py-1">
                                <v-list-item prepend-icon="mdi-pencil-outline" title="编辑" @click="emit('edit')" />
                                <v-list-item prepend-icon="mdi-content-copy" title="复制" @click="emit('duplicate')" />
                                <v-list-item
                                    :prepend-icon="task.status === 'disabled' ? 'mdi-play-circle-outline' : 'mdi-pause-circle-outline'"
                                    :title="task.status === 'disabled' ? '启用' : '禁用'" @click="emit('toggle-status')" />
                                <v-divider />
                                <v-list-item prepend-icon="mdi-delete-outline" title="删除" base-color="error"
                                    @click="emit('delete')" />
                            </v-list>
                        </v-menu>
                    </div>
                </div>
            </v-card-item>

            <v-tabs :model-value="activeTab" class="px-2" density="compact"
                @update:model-value="emit('update:activeTab', $event)">
                <v-tab value="details" size="small" class="text-none font-weight-medium text-body-large">详情</v-tab>
                <v-tab value="runs" size="small" class="text-none font-weight-medium text-body-large">运行记录</v-tab>
            </v-tabs>
            <v-divider />

            <v-window :model-value="activeTab" @update:model-value="emit('update:activeTab', $event)">
                <v-window-item value="details">
                    <v-card-text class="pa-5">
                        <v-row density="compact">
                            <v-col cols="12" sm="4">
                                <v-card rounded="lg" elevation="0" border>
                                    <v-card-text class="pa-4">
                                        <div class="text-caption text-medium-emphasis mb-1">模式</div>
                                        <div class="d-flex align-center ga-2 text-body-large">
                                            <v-icon size="16">{{ MODE_ICON[task.execution_mode] }}</v-icon>
                                            <span class="font-weight-medium">{{ MODE_LABEL[task.execution_mode]
                                                }}</span>
                                        </div>
                                    </v-card-text>
                                </v-card>
                            </v-col>
                            <v-col cols="12" sm="4">
                                <v-card rounded="lg" elevation="0" border>
                                    <v-card-text class="pa-4">
                                        <div class="text-caption text-medium-emphasis mb-1">调度</div>
                                        <div class="font-weight-medium text-body-large">
                                            {{ task.cron_expression ? cronToHuman(task.cron_expression) : '仅手动执行'
                                            }}
                                        </div>
                                    </v-card-text>
                                </v-card>
                            </v-col>
                            <v-col cols="12" sm="4">
                                <v-card rounded="lg" elevation="0" border>
                                    <v-card-text class="pa-4">
                                        <div class="text-caption text-medium-emphasis mb-1">上次运行</div>
                                        <div class="font-weight-medium text-body-large">
                                            {{ task.last_run_at ? formatDateTime(task.last_run_at) : '从未运行' }}
                                        </div>
                                    </v-card-text>
                                </v-card>
                            </v-col>
                        </v-row>

                        <v-alert v-if="task.last_run_status === 'failed'" type="error" variant="tonal" rounded="lg"
                            class="mt-3" icon="false" density="compact">
                            <div class="d-flex align-center ga-2 text-body-large font-weight-medium">
                                <v-icon size="14">mdi-alert-circle-outline</v-icon>
                                <span>最近一次运行失败，请到“运行记录”查看日志。</span>
                            </div>
                        </v-alert>

                        <v-card rounded="lg" elevation="0" border class="mt-3">
                            <v-card-text class="pa-4">
                                <v-row density="compact">
                                    <v-col cols="12" sm="6" md="3">
                                        <div class="text-uppercase text-caption text-medium-emphasis mb-1">ID</div>
                                        <div class="text-body-large" style="overflow-wrap: anywhere;">{{ task.id }}
                                        </div>
                                    </v-col>
                                    <v-col cols="12" sm="6" md="3">
                                        <div class="text-uppercase text-caption text-medium-emphasis mb-1">更新时间</div>
                                        <div class="text-body-large">{{ formatDateTime(task.updated_at) }}</div>
                                    </v-col>
                                    <v-col cols="12" sm="6" md="3" v-if="task.cron_expression">
                                        <div class="text-uppercase text-caption text-medium-emphasis mb-1">Cron</div>
                                        <div class="text-body-large" style="overflow-wrap: anywhere;">{{
                                            task.cron_expression }}</div>
                                    </v-col>
                                    <v-col cols="12" sm="6" md="3">
                                        <div class="text-uppercase text-caption text-medium-emphasis mb-1">环境变量</div>
                                        <div class="text-body-large" style="overflow-wrap: anywhere;">
                                            {{task.env_var_refs.length ? task.env_var_refs.map((item) =>
                                                item.key).join(', ') : '无'
                                            }}
                                        </div>
                                    </v-col>
                                </v-row>
                            </v-card-text>
                        </v-card>

                        <v-card v-if="task.description" rounded="lg" elevation="0" border class="mt-3">
                            <v-card-text class="pa-4">
                                <div class="text-caption text-medium-emphasis mb-2">描述</div>
                                <div class="text-body-large" style="white-space: pre-wrap;">{{ task.description }}</div>
                            </v-card-text>
                        </v-card>

                        <v-card rounded="lg" elevation="0" border class="mt-3 overflow-hidden">
                            <v-card-item>
                                <v-card-title class="text-body-large font-weight-semibold">内容</v-card-title>
                            </v-card-item>
                            <v-divider />
                            <div class="task-editor-preview">
                                <MonacoEditor :model-value="task.payload"
                                    :language="task.execution_mode === 'script' ? 'python' : 'markdown'"
                                    :read-only="true" :show-line-numbers="task.execution_mode === 'script'" />
                            </div>
                        </v-card>
                    </v-card-text>
                </v-window-item>

                <v-window-item value="runs">
                    <v-card-text class="pa-5">
                        <div class="d-flex align-center justify-space-between ga-3 flex-wrap mb-3">
                            <v-chip-group :model-value="runStatusFilter" mandatory selected-class="text-primary"
                                @update:model-value="emit('update:runStatusFilter', $event)">
                                <v-chip v-for="item in runStatusFilters" :key="item.value" :value="item.value"
                                    size="small" rounded="lg" filter variant="text">
                                    {{ item.label }}
                                </v-chip>
                            </v-chip-group>
                            <v-btn v-if="selectedRun && canCancelRun(selectedRun)" variant="text" rounded="lg"
                                size="small" color="warning" @click="emit('cancel-run')">
                                取消运行
                            </v-btn>
                        </div>

                        <v-row density="compact" align="stretch">
                            <v-col cols="12" md="5" class="d-flex">
                                <v-card rounded="lg" elevation="0" border min-height="380"
                                    class="d-flex flex-column w-100">
                                    <v-progress-linear v-if="runsLoading" indeterminate />
                                    <v-list v-else-if="runs.length" lines="two" class="py-2">
                                        <v-list-item v-for="run in runs" :key="run.id"
                                            :active="selectedRunId === run.id" rounded="lg" color="primary" slim
                                            prepend-gap="10" :ripple="false" class="mx-2 mb-1 py-1"
                                            @click="emit('select-run', run.id)">
                                            <template #prepend>
                                                <v-avatar size="24" rounded="lg">
                                                    <v-icon :color="RUN_STATUS_COLOR[run.status]">{{
                                                        RUN_STATUS_ICON[run.status] }}</v-icon>
                                                </v-avatar>
                                            </template>
                                            <v-list-item-title class="text-body-large font-weight-medium">{{
                                                RUN_STATUS_LABEL[run.status] }}</v-list-item-title>
                                            <v-list-item-subtitle class="text-caption text-medium-emphasis">{{
                                                formatDateTime(run.started_at)
                                                }}</v-list-item-subtitle>
                                            <template #append>
                                                <v-chip size="x-small" variant="tonal">
                                                    <v-icon start size="12">{{ TRIGGER_ICON[run.trigger] }}</v-icon>
                                                    {{ TRIGGER_LABEL[run.trigger] }}
                                                </v-chip>
                                            </template>
                                        </v-list-item>
                                    </v-list>
                                    <v-empty-state v-else icon="mdi-history" title="" text="暂无运行记录" />
                                </v-card>
                            </v-col>

                            <v-col cols="12" md="7" class="d-flex">
                                <v-card rounded="lg" elevation="0" border min-height="380"
                                    class="d-flex flex-column w-100">
                                    <template v-if="selectedRun">
                                        <v-card-item>
                                            <div class="d-flex align-center justify-space-between ga-3 flex-wrap">
                                                <div class="d-flex align-center ga-2 flex-wrap">
                                                    <div class="text-body-large font-weight-medium">运行详情</div>
                                                    <v-chip :color="RUN_STATUS_COLOR[selectedRun.status]" size="small"
                                                        variant="tonal">
                                                        {{ RUN_STATUS_LABEL[selectedRun.status] }}
                                                    </v-chip>
                                                    <v-chip size="small" variant="text">
                                                        <v-icon start size="12">{{ TRIGGER_ICON[selectedRun.trigger]
                                                            }}</v-icon>
                                                        {{ TRIGGER_LABEL[selectedRun.trigger] }}
                                                    </v-chip>
                                                </div>
                                                <div class="text-caption text-medium-emphasis">
                                                    {{ formatDateTime(selectedRun.started_at) }}
                                                </div>
                                            </div>
                                        </v-card-item>
                                        <v-divider />
                                        <v-alert v-if="selectedRun.error_message" type="error" variant="tonal"
                                            rounded="lg" class="mx-4 mt-3 mb-0 align-self-start flex-0-0" icon="false"
                                            density="compact" style="width: calc(100% - 32px);">
                                            <div class="d-flex align-center ga-2 text-body-large font-weight-medium">
                                                <v-icon size="14">mdi-alert-circle-outline</v-icon>
                                                <span>{{ selectedRun.error_message }}</span>
                                            </div>
                                        </v-alert>
                                        <v-progress-linear v-if="logsLoading" indeterminate />
                                        <v-card-text v-else class="task-log-panel">
                                            <pre v-if="selectedRunLogs.length"
                                                class="task-log-text">{{ selectedRunLogs.join('\n') }}</pre>
                                            <div v-else class="text-medium-emphasis">暂无日志输出</div>
                                        </v-card-text>
                                    </template>
                                    <v-empty-state v-else icon="mdi-file-document-outline" title=""
                                        text="请选择一条运行记录查看日志" />
                                </v-card>
                            </v-col>
                        </v-row>
                    </v-card-text>
                </v-window-item>
            </v-window>
        </template>

        <v-empty-state v-else icon="mdi-robot-outline" title="" text="请选择一个任务查看详情" class="h-100 pt-12" />
    </v-card>
</template>

<script setup lang="ts">
    import MonacoEditor from '@/components/editor/MonacoEditor.vue'
    import type { Run, Task } from '@/utils/tasks'
    import {
        cronToHuman,
        formatDateTime,
        MODE_ICON,
        MODE_LABEL,
        RUN_STATUS_LABEL,
        RUN_STATUS_COLOR,
        RUN_STATUS_ICON,
        TASK_STATUS_LABEL,
        TASK_STATUS_COLOR,
        TASK_STATUS_ICON,
        TRIGGER_ICON,
        TRIGGER_LABEL,
    } from '@/utils/tasks'

    defineProps<{
        task: Task | null
        activeTab: 'details' | 'runs'
        triggering: boolean
        runStatusFilter: string
        runStatusFilters: readonly { label: string, value: string }[]
        runs: Run[]
        runsLoading: boolean
        selectedRunId: string | null
        selectedRun: Run | null
        selectedRunLogs: string[]
        logsLoading: boolean
    }>()

    const emit = defineEmits<{
        'update:activeTab': [value: 'details' | 'runs']
        trigger: []
        edit: []
        duplicate: []
        'toggle-status': []
        delete: []
        'update:runStatusFilter': [value: string]
        'cancel-run': []
        'select-run': [runId: string]
    }>()

    function canCancelRun (run: Run) {
        return run.status === 'pending' || run.status === 'running'
    }
</script>

<style scoped>
    .task-menu :deep(.v-list-item) {
        min-height: 36px;
        padding-inline: 14px;
    }

    .task-menu :deep(.v-list-item-title) {
        font-size: 0.92rem;
        font-weight: 500;
    }

    .task-menu :deep(.v-icon) {
        font-size: 18px;
    }

    :deep(.v-alert__prepend) {
        display: none;
    }

    :deep(.v-alert__content) {
        padding: 0;
    }

    :deep(.v-alert__underlay) {
        display: none;
    }

    .task-editor-preview {
        height: 400px;
    }

    .task-log-panel {
        min-height: 300px;
    }

    .task-log-text {
        margin: 0;
        white-space: pre-wrap;
        word-break: break-word;
        font-family: Consolas, "SFMono-Regular", Menlo, monospace;
        font-size: 0.78rem;
        line-height: 1.55;
    }
</style>
