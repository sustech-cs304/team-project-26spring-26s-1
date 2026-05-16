<template>
    <v-card rounded="0" elevation="0" class="h-100 d-flex flex-column" color="transparent">
        <template v-if="task">
            <div class="task-details-scroll flex-grow-1">
                <v-card-text class="task-content-shell task-pane-body">
                    <div class="task-overview-grid">
                        <v-sheet rounded="lg" border color="transparent" class="task-section pa-3">
                            <div class="task-section-title">任务概览</div>
                            <div class="task-description mt-2">
                                {{ task.description || '暂无描述' }}
                            </div>

                            <div class="task-detail-list mt-2">
                                <div class="task-detail-row">
                                    <span>模式</span>
                                    <strong class="d-inline-flex align-center ga-2">
                                        <v-icon size="16">{{ MODE_ICON[task.execution_mode] }}</v-icon>
                                        {{ MODE_LABEL[task.execution_mode] }}
                                    </strong>
                                </div>
                                <div class="task-detail-row">
                                    <span>更新时间</span>
                                    <strong>{{ formatDateTime(task.updated_at) }}</strong>
                                </div>
                            </div>
                        </v-sheet>

                        <v-sheet rounded="lg" border color="transparent" class="task-section pa-3">
                            <div class="task-section-title">运行设置</div>
                            <div class="task-detail-list mt-2">
                                <div class="task-detail-row">
                                    <span>状态</span>
                                    <v-chip size="x-small" variant="tonal">
                                        <v-icon start size="12">{{ TASK_STATUS_ICON[task.status] }}</v-icon>
                                        {{ TASK_STATUS_LABEL[task.status] }}
                                    </v-chip>
                                </div>
                                <div class="task-detail-row">
                                    <span>调度</span>
                                    <strong>{{ task.cron_expression ? cronToHuman(task.cron_expression) : '仅手动执行'
                                    }}</strong>
                                </div>
                                <div class="task-detail-row">
                                    <span>上次运行</span>
                                    <strong>{{ task.last_run_at ? formatDateTime(task.last_run_at) : '从未运行' }}</strong>
                                </div>
                            </div>
                        </v-sheet>
                    </div>

                    <v-sheet rounded="lg" border color="transparent" class="task-section task-runs-section mt-2">
                        <div class="d-flex align-center justify-space-between ga-3 px-3 py-2">
                            <div class="task-section-title">运行记录</div>
                            <div class="d-flex align-center ga-2">
                                <v-chip-group :model-value="runStatusFilter" mandatory
                                    selected-class="task-filter-active"
                                    @update:model-value="emit('update:runStatusFilter', $event)">
                                    <v-chip v-for="item in runStatusFilters" :key="item.value" :value="item.value"
                                        size="x-small" rounded="lg" filter variant="tonal">
                                        {{ item.label }}
                                    </v-chip>
                                </v-chip-group>
                                <v-btn v-if="selectedRun && canCancelRun(selectedRun)" variant="tonal" rounded="lg"
                                    size="small" color="warning" @click="emit('cancel-run')">
                                    取消运行
                                </v-btn>
                            </div>
                        </div>
                        <div class="task-runs-layout">
                            <div class="task-runs-list">
                                <v-progress-linear v-if="runsLoading" indeterminate />
                                <v-list v-else-if="runs.length" density="compact" bg-color="transparent" class="pa-1">
                                    <v-list-item v-for="(run, index) in runs" :key="run.id"
                                        :active="selectedRunId === run.id" rounded="lg"
                                        active-class="theme-active-list-item" prepend-gap="8" :ripple="false"
                                        class="px-2 py-1 my-1" @click="emit('select-run', run.id)">
                                        <template #prepend>
                                            <v-icon class="run-status-icon" size="16">{{
                                                RUN_STATUS_ICON[run.status] }}</v-icon>
                                        </template>
                                        <v-list-item-title class="task-run-title font-weight-medium">
                                            运行 {{ runs.length - index }}
                                        </v-list-item-title>
                                        <template #append>
                                            <v-icon size="14">mdi-chevron-right</v-icon>
                                        </template>
                                    </v-list-item>
                                </v-list>
                                <div v-else class="text-center text-body-2 text-medium-emphasis py-6">
                                    暂无运行记录
                                </div>
                            </div>

                            <div class="task-run-detail">
                                <template v-if="selectedRun">
                                    <v-progress-linear v-if="logsLoading" indeterminate />
                                    <v-sheet v-else class="task-log-editor" color="transparent">
                                        <MonacoEditor :model-value="selectedRunLogs.join('\n') || '暂无日志输出'"
                                            language="plaintext" :read-only="true" :show-line-numbers="false" />
                                    </v-sheet>
                                </template>
                                <div v-else class="text-center text-body-2 text-medium-emphasis py-6">
                                    请选择一条运行记录查看日志
                                </div>
                            </div>
                        </div>
                    </v-sheet>
                </v-card-text>
            </div>
        </template>

        <div v-else class="h-100 d-flex align-center justify-center text-body-2 text-medium-emphasis">
            请选择一个任务查看详情
        </div>
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
        RUN_STATUS_ICON,
        TASK_STATUS_LABEL,
        TASK_STATUS_ICON,
    } from '@/utils/tasks'

    defineProps<{
        task: Task | null
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

    .task-details-scroll {
        min-height: 0;
        overflow: hidden;
    }

    .task-pane-body {
        display: flex;
        flex-direction: column;
        height: 100%;
        min-height: 0;
        padding-block: 6px 16px;
    }

    .task-section {
        background: rgba(var(--v-theme-on-surface), 0.018) !important;
    }

    .task-overview-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
        flex-shrink: 0;
    }

    .task-section-title {
        font-size: 0.875rem;
        font-weight: 700;
        line-height: 1.25rem;
    }

    .task-description {
        color: rgba(var(--v-theme-on-surface), 0.68);
        font-size: 0.8125rem;
        line-height: 1.35;
        white-space: pre-wrap;
    }

    .task-detail-list {
        display: grid;
        gap: 6px;
    }

    .task-detail-row {
        display: grid;
        grid-template-columns: 76px minmax(0, 1fr);
        align-items: center;
        gap: 10px;
        min-height: 22px;
        font-size: 0.8125rem;
    }

    .task-detail-row>span {
        color: rgba(var(--v-theme-on-surface), 0.62);
    }

    .task-detail-row strong {
        min-width: 0;
        font-weight: 600;
    }

    .task-detail-row> :deep(.v-chip) {
        justify-self: start;
        width: fit-content;
        max-width: 100%;
    }

    :deep(.task-filter-active) {
        background: rgba(var(--v-theme-on-surface), 0.1) !important;
        color: rgb(var(--v-theme-on-surface)) !important;
    }

    .run-status-icon {
        color: rgba(var(--v-theme-on-surface), 0.72) !important;
        flex-shrink: 0;
    }

    .task-runs-section {
        display: flex;
        flex: 1 1 auto;
        flex-direction: column;
        min-height: 0;
        overflow: hidden;
    }

    .task-runs-layout {
        display: grid;
        flex: 1 1 auto;
        grid-template-columns: minmax(128px, 164px) minmax(0, 1fr);
        min-height: 0;
        overflow: hidden;
    }

    .task-runs-list {
        min-height: 0;
        overflow-y: auto;
    }

    .task-run-title {
        font-size: 0.8125rem;
        line-height: 1.25rem;
    }

    .task-run-detail {
        display: flex;
        flex-direction: column;
        min-width: 0;
        min-height: 0;
        overflow: hidden;
    }

    .task-log-editor {
        flex: 1 1 auto;
        height: auto;
        min-height: 0;
    }

    @media (max-width: 900px) {

        .task-overview-grid,
        .task-runs-layout {
            grid-template-columns: 1fr;
        }
    }
</style>
