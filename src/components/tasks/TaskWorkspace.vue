<template>
    <v-layout class="task-workspace h-100 overflow-hidden min-height-0">
        <v-navigation-drawer v-model="drawer" permanent width="250" color="surface" floating class="task-sidebar min-height-0">
            <template v-if="!taskSearchMode">
                <v-list nav density="compact" class="pb-0">
                    <v-list-item title="任务" rounded="lg" slim prepend-gap="6" :ripple="false"
                        :active="currentView === 'tasks'" active-class="theme-active-list-item"
                        @click="currentView = 'tasks'">
                        <template #prepend>
                            <v-icon size="small">mdi-format-list-bulleted-square</v-icon>
                        </template>
                    </v-list-item>
                    <v-list-item title="搜索任务" rounded="lg" slim prepend-gap="6" :ripple="false" link
                        @click="enterTaskSearchMode">
                        <template #prepend>
                            <v-icon size="small">mdi-text-box-search-outline</v-icon>
                        </template>
                    </v-list-item>
                    <v-list-item title="环境变量" rounded="lg" slim prepend-gap="6" :ripple="false"
                        :active="currentView === 'env-vars'" active-class="theme-active-list-item"
                        @click="openEnvVars">
                        <template #prepend>
                            <v-icon size="small">mdi-key-outline</v-icon>
                        </template>
                    </v-list-item>
                </v-list>
            </template>
            <div v-else class="px-2 py-2">
                <v-text-field :model-value="search" placeholder="搜索任务" variant="solo-filled" flat
                    density="compact" hide-details clearable autofocus prepend-inner-icon="mdi-magnify"
                    rounded="lg" class="text-body-2"
                    @update:model-value="handleSearchUpdate(String($event ?? ''))"
                    @click:clear="exitTaskSearchMode" @keydown.esc="exitTaskSearchMode" />
                <div class="d-flex justify-end mt-1">
                    <v-btn size="x-small" variant="text" @click="exitTaskSearchMode">取消</v-btn>
                </div>
            </div>

            <div v-if="currentView === 'tasks'" class="d-flex align-center justify-space-between px-3 pt-2 pb-1">
                <v-card-subtitle class="pa-0 text-caption">
                    {{ taskSearchMode ? '搜索结果' : '任务' }}
                </v-card-subtitle>
            </div>

            <template v-if="currentView === 'tasks'">
                <TaskListPane :loading="loading" :search-mode="taskSearchMode" :search="search"
                    :status-filter="statusFilter" :status-filters="statusFilters" :tasks="filteredTasks"
                    :selected-task-id="selectedTaskId" @update:status-filter="statusFilter = $event as StatusFilter"
                    @select="selectTask" @edit="handleListEdit" @duplicate="handleListDuplicate"
                    @toggle-status="handleListToggleStatus" @delete="handleListDelete" />
            </template>
        </v-navigation-drawer>

        <v-app-bar flat height="48" color="background" class="task-app-bar">
            <template #prepend>
                <v-btn :icon="drawer ? 'mdi-menu-open' : 'mdi-menu'" variant="text" size="small" :ripple="false"
                    @click="drawer = !drawer" />
                <v-btn v-if="currentView === 'tasks'" icon="mdi-plus-box-outline" size="small" variant="text"
                    :ripple="false" @click="handleOpenCreate" />
            </template>

            <div v-if="currentView === 'tasks' && selectedTask" class="task-app-title">
                {{ selectedTask.name }}
            </div>

            <template #append>
                <div v-if="currentView === 'tasks' && selectedTask" class="d-flex align-center ga-1 pr-2">
                    <v-btn :icon="selectedTask.status === 'running' ? 'mdi-progress-clock' : 'mdi-play'" variant="text"
                        size="small" :ripple="false" :aria-label="selectedTask.status === 'running' ? '运行中' : '运行任务'"
                        :loading="triggering" :disabled="selectedTask.status === 'running'" @click="triggerNow" />
                    <v-menu location="bottom end" :offset="4">
                        <template #activator="{ props }">
                            <v-btn v-bind="props" icon="mdi-dots-horizontal" variant="text" size="small"
                                :ripple="false" />
                        </template>
                        <v-list rounded="lg" density="compact" width="136" class="py-1">
                            <v-list-item title="编辑" density="compact" @click="handleOpenEdit">
                                <template #prepend>
                                    <v-icon size="16">mdi-pencil-outline</v-icon>
                                </template>
                            </v-list-item>
                            <v-list-item title="复制" density="compact" @click="handleOpenDuplicate">
                                <template #prepend>
                                    <v-icon size="16">mdi-content-copy</v-icon>
                                </template>
                            </v-list-item>
                            <v-list-item :title="selectedTask.status === 'disabled' ? '启用' : '禁用'"
                                density="compact" @click="toggleTaskStatus">
                                <template #prepend>
                                    <v-icon size="16">
                                        {{ selectedTask.status === 'disabled' ? 'mdi-play-circle-outline' :
                                            'mdi-pause-circle-outline' }}
                                    </v-icon>
                                </template>
                            </v-list-item>
                            <v-divider />
                            <v-list-item title="删除" base-color="error" density="compact" @click="deleteDialog = true">
                                <template #prepend>
                                    <v-icon size="16">mdi-delete-outline</v-icon>
                                </template>
                            </v-list-item>
                        </v-list>
                    </v-menu>
                </div>
            </template>
        </v-app-bar>

        <v-main class="task-main h-100 overflow-hidden min-height-0">
            <div class="task-route-panel">
                <TaskDetailsPane v-if="currentView === 'tasks'" :task="selectedTask"
                    :triggering="triggering" :run-status-filter="runStatusFilter"
                    :run-status-filters="runStatusFilters" :runs="runs" :runs-loading="runsLoading"
                    :selected-run-id="selectedRunId" :selected-run="selectedRun"
                    :selected-run-logs="selectedRunLogs" :logs-loading="logsLoading"
                    @trigger="triggerNow" @edit="handleOpenEdit" @duplicate="handleOpenDuplicate"
                    @toggle-status="toggleTaskStatus" @delete="deleteDialog = true"
                    @update:run-status-filter="runStatusFilter = $event as RunFilter"
                    @cancel-run="cancelSelectedRun" @select-run="selectRun" />
                <TaskEnvVarsPane v-else :env-vars="envVars" :loading="envVarsLoading" :saving="envVarSaving"
                    :deleting-key="deletingEnvKey" :latest-saved-key="latestEnvKey" @save="saveEnvVar"
                    @delete="removeEnvVarEntry" />
            </div>
        </v-main>

        <TaskEditorDialog v-model="editorDialog" :title="editorTitle" :action-label="editorActionLabel" :saving="saving"
            :form="editorForm" :cron-presets="cronPresets" :saved-env-vars="envVars" @add-env-var="handleAddEnvVar"
            @request-env-vars-setup="handleRequestEnvVarSetup" @remove-env-var="removeEnvVar" @save="saveTask" />

        <TaskDeleteDialog v-model="deleteDialog" :loading="deleting" @confirm="confirmDelete" />

        <v-snackbar v-model="snackbar.show" :color="snackbar.color" location="top" timeout="3000">
            {{ snackbar.text }}
        </v-snackbar>
    </v-layout>
</template>

<script setup lang="ts">
    import { statusFilters, runStatusFilters, type RunFilter, type StatusFilter, cronPresets, useTaskWorkspace } from '@/composables/useTaskWorkspace'
    import TaskDeleteDialog from '@/components/tasks/TaskDeleteDialog.vue'
    import TaskDetailsPane from '@/components/tasks/TaskDetailsPane.vue'
    import TaskEditorDialog from '@/components/tasks/TaskEditorDialog.vue'
    import TaskEnvVarsPane from '@/components/tasks/TaskEnvVarsPane.vue'
    import TaskListPane from '@/components/tasks/TaskListPane.vue'
    import { useRoute } from 'vue-router'

    const route = useRoute()
    const drawer = ref(true)
    const currentView = ref<'tasks' | 'env-vars'>('tasks')
    const taskSearchMode = ref(false)

    const {
        cancelSelectedRun,
        confirmDelete,
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
        saveEnvVar,
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
        showSnackbar,
        snackbar,
        statusFilter,
        toggleTaskStatus,
        triggerNow,
        triggering,
    } = useTaskWorkspace()

    function openEnvVars () {
        exitTaskSearchMode()
        currentView.value = 'env-vars'
        loadEnvVarList()
    }

    function handleSearchUpdate (value: string) {
        search.value = value
        if (!value.trim()) {
            statusFilter.value = 'all'
        }
    }

    function enterTaskSearchMode () {
        currentView.value = 'tasks'
        taskSearchMode.value = true
        search.value = ''
        statusFilter.value = 'all'
    }

    function exitTaskSearchMode () {
        taskSearchMode.value = false
        search.value = ''
        statusFilter.value = 'all'
    }

    async function handleOpenCreate () {
        currentView.value = 'tasks'
        await ensureEnvVarsLoaded()
        openCreate()
    }

    async function handleOpenEdit () {
        currentView.value = 'tasks'
        await ensureEnvVarsLoaded()
        openEdit()
    }

    async function handleOpenDuplicate () {
        currentView.value = 'tasks'
        await ensureEnvVarsLoaded()
        openDuplicate()
    }

    async function handleListEdit (taskId: string) {
        selectTask(taskId)
        await handleOpenEdit()
    }

    async function handleListDuplicate (taskId: string) {
        selectTask(taskId)
        await handleOpenDuplicate()
    }

    async function handleListToggleStatus (taskId: string) {
        selectTask(taskId)
        await toggleTaskStatus()
    }

    function handleListDelete (taskId: string) {
        selectTask(taskId)
        deleteDialog.value = true
    }

    async function handleRequestEnvVarSetup () {
        if (editorDialog.value && hasEditorChanges.value) {
            const shouldSave = window.confirm(
                '当前任务有未保存修改。是否先保存再前往环境变量页面？\n点击“确定”保存并跳转，点击“取消”不保存直接跳转。'
            )

            if (shouldSave) {
                const saved = await saveTask()
                if (!saved) return
            } else {
                editorDialog.value = false
            }
        } else if (editorDialog.value) {
            editorDialog.value = false
        }

        currentView.value = 'env-vars'
        await loadEnvVarList()
        showSnackbar('请先创建环境变量后再回到任务配置')
    }

    async function handleAddEnvVar () {
        await ensureEnvVarsLoaded()

        if (!envVars.value.length) {
            await handleRequestEnvVarSetup()
            return
        }

        const selectedKeys = new Set(
            editorForm.env_var_refs
                .map(item => item.key.trim())
                .filter(Boolean)
        )
        const firstAvailable = envVars.value.find(item => !selectedKeys.has(item.key))

        if (!firstAvailable) return

        editorForm.env_var_refs.push({
            key: firstAvailable.key,
        })
    }


    watch(
        () => [route.query.taskId, route.query.runId],
        ([taskId, runId]) => {
            if (typeof taskId === 'string' && taskId) {
                currentView.value = 'tasks'
                if (selectedTaskId.value !== taskId) {
                    selectTask(taskId)
                }
            }

            if (typeof runId === 'string' && runId) {
                currentView.value = 'tasks'
                if (selectedRunId.value !== runId) {
                    selectRun(runId)
                }
            }
        },
        { immediate: true }
    )
</script>

<style scoped>
    .task-workspace {
        --task-content-radius: 8px;
        background: rgb(var(--v-theme-surface));
    }

    .task-sidebar {
        background: rgb(var(--v-theme-surface)) !important;
    }

    .task-app-bar {
        background: rgb(var(--v-theme-background)) !important;
        border-top-left-radius: var(--task-content-radius) !important;
        overflow: hidden;
    }

    .task-app-bar :deep(.v-toolbar__content) {
        position: relative;
    }

    .task-app-title {
        position: absolute;
        left: 50%;
        max-width: min(42vw, 520px);
        overflow: hidden;
        font-size: 0.875rem;
        font-weight: 600;
        line-height: 1.25rem;
        text-overflow: ellipsis;
        transform: translateX(-50%);
        white-space: nowrap;
    }

    .task-main {
        background: transparent;
    }

    .task-route-panel {
        height: 100%;
        min-height: 0;
        overflow: hidden;
        background: rgb(var(--v-theme-background));
        border-bottom-left-radius: var(--task-content-radius);
    }

    .task-workspace :deep(.theme-active-list-item) {
        background: rgba(var(--v-theme-on-surface), 0.05) !important;
        color: rgb(var(--v-theme-on-surface)) !important;
    }

    .task-workspace :deep(.v-list-item--active > .v-list-item__overlay),
    .task-workspace :deep(.theme-active-list-item > .v-list-item__overlay) {
        opacity: 0 !important;
    }

    .task-sidebar :deep(.theme-active-list-item .v-icon) {
        color: currentColor !important;
    }

    .task-sidebar :deep(.theme-active-list-item .v-list-item-subtitle) {
        color: rgba(var(--v-theme-on-surface), 0.62) !important;
        opacity: 1;
    }
</style>
