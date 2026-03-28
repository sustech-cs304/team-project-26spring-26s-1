<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0">
        <v-sheet color="transparent" class="flex-grow-1 overflow-y-auto">
            <v-container max-width="1100" class="px-5 py-5">
                <div class="d-flex align-center justify-space-between mb-5 ga-3 flex-wrap">
                    <div class="text-h6 font-weight-bold">Tasks</div>
                    <v-btn color="primary" rounded="lg" size="small" prepend-icon="mdi-plus" @click="openCreate">
                        New task
                    </v-btn>
                </div>

                <v-row class="ma-0" density="compact">
                    <v-col cols="12" md="4" class="pa-0 pr-md-3">
                        <TaskListPane
                            :loading="loading"
                            :search="search"
                            :status-filter="statusFilter"
                            :status-filters="statusFilters"
                            :tasks="filteredTasks"
                            :selected-task-id="selectedTaskId"
                            @update:search="search = $event"
                            @update:status-filter="statusFilter = $event as StatusFilter"
                            @select="selectTask"
                        />
                    </v-col>

                    <v-col cols="12" md="8" class="pa-0 pl-md-3 mt-3 mt-md-0">
                        <TaskDetailsPane
                            :task="selectedTask"
                            :active-tab="activeTab"
                            :triggering="triggering"
                            :run-status-filter="runStatusFilter"
                            :run-status-filters="runStatusFilters"
                            :runs="runs"
                            :runs-loading="runsLoading"
                            :selected-run-id="selectedRunId"
                            :selected-run="selectedRun"
                            :selected-run-logs="selectedRunLogs"
                            :logs-loading="logsLoading"
                            @update:active-tab="activeTab = $event"
                            @trigger="triggerNow"
                            @edit="openEdit"
                            @duplicate="openDuplicate"
                            @toggle-status="toggleTaskStatus"
                            @delete="deleteDialog = true"
                            @update:run-status-filter="runStatusFilter = $event as RunFilter"
                            @cancel-run="cancelSelectedRun"
                            @select-run="selectRun"
                        />
                    </v-col>
                </v-row>
            </v-container>
        </v-sheet>

        <TaskEditorDialog
            v-model="editorDialog"
            :title="editorTitle"
            :action-label="editorActionLabel"
            :saving="saving"
            :form="editorForm"
            :cron-presets="cronPresets"
            @add-env-var="addEnvVar"
            @remove-env-var="removeEnvVar"
            @save="saveTask"
        />

        <TaskDeleteDialog v-model="deleteDialog" :loading="deleting" @confirm="confirmDelete" />

        <v-snackbar v-model="snackbar.show" :color="snackbar.color" location="top" timeout="3000">
            {{ snackbar.text }}
        </v-snackbar>
    </v-container>
</template>

<script setup lang="ts">
    import { statusFilters, runStatusFilters, type RunFilter, type StatusFilter, cronPresets, useTaskWorkspace } from '@/composables/useTaskWorkspace'
    import TaskDeleteDialog from '@/components/tasks/TaskDeleteDialog.vue'
    import TaskDetailsPane from '@/components/tasks/TaskDetailsPane.vue'
    import TaskEditorDialog from '@/components/tasks/TaskEditorDialog.vue'
    import TaskListPane from '@/components/tasks/TaskListPane.vue'

    const {
        activeTab,
        addEnvVar,
        cancelSelectedRun,
        confirmDelete,
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
        toggleTaskStatus,
        triggerNow,
        triggering,
    } = useTaskWorkspace()
</script>
