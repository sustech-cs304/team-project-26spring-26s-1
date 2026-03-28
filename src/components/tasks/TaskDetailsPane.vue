<template>
    <v-card rounded="lg" elevation="0" border min-height="680">
        <template v-if="task">
            <v-card-item class="px-5 pt-4 pb-2">
                <div class="d-flex align-start justify-space-between ga-3 flex-wrap">
                    <div class="d-flex align-center ga-2 flex-wrap">
                        <div class="text-body-1 font-weight-bold">{{ task.name }}</div>
                        <v-chip :color="TASK_STATUS_COLOR[task.status]" size="small" variant="tonal">
                            <v-icon start size="14">{{ TASK_STATUS_ICON[task.status] }}</v-icon>
                            {{ task.status }}
                        </v-chip>
                    </div>

                    <div class="d-flex align-center ga-2">
                        <v-btn color="primary" rounded="lg" size="small" prepend-icon="mdi-play" :loading="triggering" @click="emit('trigger')">
                            Run now
                        </v-btn>
                        <v-menu>
                            <template #activator="{ props }">
                                <v-btn v-bind="props" icon="mdi-dots-horizontal" variant="text" rounded="lg" size="small" />
                            </template>
                            <v-list rounded="lg" density="compact" class="task-menu py-1">
                                <v-list-item prepend-icon="mdi-pencil-outline" title="Edit" @click="emit('edit')" />
                                <v-list-item prepend-icon="mdi-content-copy" title="Duplicate" @click="emit('duplicate')" />
                                <v-list-item
                                    :prepend-icon="task.status === 'disabled' ? 'mdi-play-circle-outline' : 'mdi-pause-circle-outline'"
                                    :title="task.status === 'disabled' ? 'Enable' : 'Disable'"
                                    @click="emit('toggle-status')"
                                />
                                <v-divider />
                                <v-list-item prepend-icon="mdi-delete-outline" title="Delete" base-color="error" @click="emit('delete')" />
                            </v-list>
                        </v-menu>
                    </div>
                </div>
            </v-card-item>

            <v-tabs :model-value="activeTab" class="px-2" density="compact" @update:model-value="emit('update:activeTab', $event)">
                <v-tab value="details" size="small">Details</v-tab>
                <v-tab value="runs" size="small">Runs</v-tab>
            </v-tabs>
            <v-divider />

            <v-window :model-value="activeTab" @update:model-value="emit('update:activeTab', $event)">
                <v-window-item value="details">
                    <v-card-text class="pa-5">
                        <v-row density="compact">
                            <v-col cols="12" sm="4">
                                <v-card rounded="lg" elevation="0" border>
                                    <v-card-text class="pa-4">
                                        <div class="text-caption text-medium-emphasis mb-1">Mode</div>
                                        <div class="d-flex align-center ga-2 text-body-2">
                                            <v-icon size="16">{{ MODE_ICON[task.execution_mode] }}</v-icon>
                                            <span class="font-weight-medium">{{ MODE_LABEL[task.execution_mode] }}</span>
                                        </div>
                                    </v-card-text>
                                </v-card>
                            </v-col>
                            <v-col cols="12" sm="4">
                                <v-card rounded="lg" elevation="0" border>
                                    <v-card-text class="pa-4">
                                        <div class="text-caption text-medium-emphasis mb-1">Schedule</div>
                                        <div class="font-weight-medium text-body-2">
                                            {{ task.cron_expression ? cronToHuman(task.cron_expression) : 'Manual only' }}
                                        </div>
                                    </v-card-text>
                                </v-card>
                            </v-col>
                            <v-col cols="12" sm="4">
                                <v-card rounded="lg" elevation="0" border>
                                    <v-card-text class="pa-4">
                                        <div class="text-caption text-medium-emphasis mb-1">Last run</div>
                                        <div class="font-weight-medium text-body-2">
                                            {{ task.last_run_at ? formatDateTime(task.last_run_at) : 'Never run' }}
                                        </div>
                                    </v-card-text>
                                </v-card>
                            </v-col>
                        </v-row>

                        <v-alert
                            v-if="task.last_run_status === 'failed'"
                            type="error"
                            variant="tonal"
                            rounded="lg"
                            class="mt-3 text-body-2"
                            text="The most recent run failed. Open Runs to inspect logs."
                        />

                        <v-card rounded="lg" elevation="0" border class="mt-3">
                            <v-list lines="two" bg-color="transparent">
                                <v-list-subheader>Overview</v-list-subheader>
                                <v-list-item title="Task ID" :subtitle="task.id" />
                                <v-list-item title="Created" :subtitle="formatDateTime(task.created_at)" />
                                <v-list-item title="Updated" :subtitle="formatDateTime(task.updated_at)" />
                                <v-list-item v-if="task.cron_expression" title="Cron expression" :subtitle="task.cron_expression" />
                                <v-list-item
                                    title="Environment variables"
                                    :subtitle="task.env_var_refs.length ? task.env_var_refs.map((item) => item.key).join(', ') : 'None'"
                                />
                            </v-list>
                        </v-card>

                        <v-card v-if="task.description" rounded="lg" elevation="0" border class="mt-3">
                            <v-card-text class="pa-4">
                                <div class="text-caption text-medium-emphasis mb-2">Description</div>
                                <div class="text-body-2" style="white-space: pre-wrap;">{{ task.description }}</div>
                            </v-card-text>
                        </v-card>

                        <v-card rounded="lg" elevation="0" border class="mt-3 overflow-hidden">
                            <v-card-item>
                                <v-card-title class="text-body-2">Payload</v-card-title>
                            </v-card-item>
                            <v-divider />
                            <div class="task-editor-preview">
                                <MonacoEditor
                                    :model-value="task.payload"
                                    :language="task.execution_mode === 'script' ? 'python' : 'markdown'"
                                    :read-only="true"
                                    :show-line-numbers="task.execution_mode === 'script'"
                                />
                            </div>
                        </v-card>
                    </v-card-text>
                </v-window-item>

                <v-window-item value="runs">
                    <v-card-text class="pa-5">
                        <div class="d-flex align-center justify-space-between ga-3 flex-wrap mb-3">
                            <v-chip-group
                                :model-value="runStatusFilter"
                                mandatory
                                selected-class="text-primary"
                                @update:model-value="emit('update:runStatusFilter', $event)"
                            >
                                <v-chip
                                    v-for="item in runStatusFilters"
                                    :key="item.value"
                                    :value="item.value"
                                    size="small"
                                    rounded="lg"
                                    filter
                                    variant="text"
                                >
                                    {{ item.label }}
                                </v-chip>
                            </v-chip-group>
                            <v-btn
                                v-if="selectedRun && canCancelRun(selectedRun)"
                                variant="text"
                                rounded="lg"
                                size="small"
                                color="warning"
                                @click="emit('cancel-run')"
                            >
                                Cancel run
                            </v-btn>
                        </div>

                        <v-row density="compact">
                            <v-col cols="12" md="5">
                                <v-card rounded="lg" elevation="0" border min-height="380">
                                    <v-progress-linear v-if="runsLoading" indeterminate />
                                    <v-list v-else-if="runs.length" lines="two" class="py-2">
                                        <v-list-item
                                            v-for="run in runs"
                                            :key="run.id"
                                            :active="selectedRunId === run.id"
                                            rounded="lg"
                                            class="mx-2 mb-1"
                                            @click="emit('select-run', run.id)"
                                        >
                                            <template #prepend>
                                                <v-avatar size="30" rounded="lg" color="surface-variant">
                                                    <v-icon :color="RUN_STATUS_COLOR[run.status]">{{ RUN_STATUS_ICON[run.status] }}</v-icon>
                                                </v-avatar>
                                            </template>
                                            <v-list-item-title class="font-weight-medium text-body-2">{{ run.status }}</v-list-item-title>
                                            <v-list-item-subtitle class="text-caption">{{ formatDateTime(run.started_at) }}</v-list-item-subtitle>
                                            <template #append>
                                                <v-chip size="x-small" variant="tonal">
                                                    <v-icon start size="12">{{ TRIGGER_ICON[run.trigger] }}</v-icon>
                                                    {{ TRIGGER_LABEL[run.trigger] }}
                                                </v-chip>
                                            </template>
                                        </v-list-item>
                                    </v-list>
                                    <v-empty-state v-else icon="mdi-history" title="" text="No runs yet" />
                                </v-card>
                            </v-col>

                            <v-col cols="12" md="7">
                                <v-card rounded="lg" elevation="0" border min-height="380">
                                    <template v-if="selectedRun">
                                        <v-card-item>
                                            <div class="d-flex align-center justify-space-between ga-3 flex-wrap">
                                                <div class="d-flex align-center ga-2 flex-wrap">
                                                    <div class="text-body-2 font-weight-medium">Run details</div>
                                                    <v-chip :color="RUN_STATUS_COLOR[selectedRun.status]" size="small" variant="tonal">
                                                        {{ selectedRun.status }}
                                                    </v-chip>
                                                    <v-chip size="small" variant="text">
                                                        <v-icon start size="12">{{ TRIGGER_ICON[selectedRun.trigger] }}</v-icon>
                                                        {{ TRIGGER_LABEL[selectedRun.trigger] }}
                                                    </v-chip>
                                                </div>
                                                <div class="text-caption text-medium-emphasis">
                                                    {{ formatDateTime(selectedRun.started_at) }}
                                                </div>
                                            </div>
                                        </v-card-item>
                                        <v-divider />
                                        <v-alert
                                            v-if="selectedRun.error_message"
                                            type="error"
                                            variant="tonal"
                                            rounded="0"
                                            class="text-body-2"
                                            :text="selectedRun.error_message"
                                        />
                                        <v-progress-linear v-if="logsLoading" indeterminate />
                                        <v-card-text v-else class="task-log-panel">
                                            <pre v-if="selectedRunLogs.length" class="task-log-text">{{ selectedRunLogs.join('\n') }}</pre>
                                            <div v-else class="text-medium-emphasis">No log output</div>
                                        </v-card-text>
                                    </template>
                                    <v-empty-state v-else icon="mdi-file-document-outline" title="" text="Select a run to inspect logs" />
                                </v-card>
                            </v-col>
                        </v-row>
                    </v-card-text>
                </v-window-item>
            </v-window>
        </template>

        <v-empty-state v-else icon="mdi-robot-outline" title="" text="Select a task to view details" class="h-100" />
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
        RUN_STATUS_COLOR,
        RUN_STATUS_ICON,
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

    function canCancelRun(run: Run) {
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
