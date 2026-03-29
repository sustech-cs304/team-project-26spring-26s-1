<template>
    <v-layout class="h-100">
        <v-navigation-drawer v-model="drawer" permanent width="250">
            <div class="pa-0 pt-1">
                <v-list nav density="compact" class="pt-1">
                    <v-list-item title="任务" rounded="lg" slim prepend-gap="6" :ripple="false"
                        :active="currentView === 'tasks'" color="primary" @click="currentView = 'tasks'">
                        <template #prepend>
                            <v-icon size="small">mdi-format-list-bulleted-square</v-icon>
                        </template>
                    </v-list-item>
                    <v-list-item title="环境变量" rounded="lg" slim prepend-gap="6" :ripple="false"
                        :active="currentView === 'env-vars'" color="primary" @click="openEnvVars">
                        <template #prepend>
                            <v-icon size="small">mdi-key-outline</v-icon>
                        </template>
                    </v-list-item>
                </v-list>
            </div>

            <v-divider />

            <div class="d-flex align-center justify-space-between px-0 pt-2 pr-2">
                <v-card-subtitle>{{ currentView === 'tasks' ? '任务' : '环境变量' }}</v-card-subtitle>
            </div>

            <template v-if="currentView === 'tasks'">
                <TaskListPane :loading="loading" :search="search" :status-filter="statusFilter"
                    :status-filters="statusFilters" :tasks="filteredTasks" :selected-task-id="selectedTaskId"
                    @update:search="search = $event" @update:status-filter="statusFilter = $event as StatusFilter"
                    @select="selectTask" />
            </template>
            <div v-else class="px-4 py-4 text-body-large text-medium-emphasis">
                在这里管理已保存的变量，并把返回的 `secret_ref` 填入任务设置中。
            </div>
        </v-navigation-drawer>

        <v-app-bar flat height="48" color="transparent">
            <template #prepend>
                <v-btn :icon="drawer ? 'mdi-menu-open' : 'mdi-menu'" variant="text" size="small" :ripple="false"
                    @click="drawer = !drawer" />
                <v-btn v-if="currentView === 'tasks'" icon="mdi-plus-box-outline" size="small" variant="text"
                    :ripple="false" @click="handleOpenCreate" />
            </template>

        </v-app-bar>

        <v-main scrollable>
            <v-sheet color="transparent" class="h-100 overflow-y-auto">
                <v-container max-width="1100" class="px-5 py-5">
                    <TaskDetailsPane v-if="currentView === 'tasks'" :task="selectedTask" :active-tab="activeTab"
                        :triggering="triggering" :run-status-filter="runStatusFilter"
                        :run-status-filters="runStatusFilters" :runs="runs" :runs-loading="runsLoading"
                        :selected-run-id="selectedRunId" :selected-run="selectedRun"
                        :selected-run-logs="selectedRunLogs" :logs-loading="logsLoading"
                        @update:active-tab="activeTab = $event" @trigger="triggerNow" @edit="handleOpenEdit"
                        @duplicate="handleOpenDuplicate" @toggle-status="toggleTaskStatus" @delete="deleteDialog = true"
                        @update:run-status-filter="runStatusFilter = $event as RunFilter"
                        @cancel-run="cancelSelectedRun" @select-run="selectRun" />
                    <TaskEnvVarsPane v-else :env-vars="envVars" :loading="envVarsLoading" :saving="envVarSaving"
                        :deleting-key="deletingEnvKey" :latest-secret-ref="latestSecretRef" @save="saveEnvVar"
                        @delete="removeEnvVarEntry" @copy="copySecretRef" />
                </v-container>
            </v-sheet>
        </v-main>

        <TaskEditorDialog v-model="editorDialog" :title="editorTitle" :action-label="editorActionLabel" :saving="saving"
            :form="editorForm" :cron-presets="cronPresets" :saved-env-vars="envVars" @add-env-var="addEnvVar"
            @remove-env-var="removeEnvVar" @save="saveTask" />

        <TaskDeleteDialog v-model="deleteDialog" :loading="deleting" @confirm="confirmDelete" />

        <v-snackbar v-model="snackbar.show" :color="snackbar.color" location="top" timeout="3000">
            {{ snackbar.text }}
        </v-snackbar>
    </v-layout>
</template>

<script setup lang="ts">
    import { deleteEnvVar, getEnvVars, upsertEnvVar } from '@/api/tasks'
    import { statusFilters, runStatusFilters, type RunFilter, type StatusFilter, cronPresets, useTaskWorkspace } from '@/composables/useTaskWorkspace'
    import TaskDeleteDialog from '@/components/tasks/TaskDeleteDialog.vue'
    import TaskDetailsPane from '@/components/tasks/TaskDetailsPane.vue'
    import TaskEditorDialog from '@/components/tasks/TaskEditorDialog.vue'
    import TaskEnvVarsPane from '@/components/tasks/TaskEnvVarsPane.vue'
    import TaskListPane from '@/components/tasks/TaskListPane.vue'
    import type { EnvVarRef } from '@/utils/tasks'
    import { copyText } from '@/utils/copyText'

    const drawer = ref(true)
    const currentView = ref<'tasks' | 'env-vars'>('tasks')
    const envVars = ref<EnvVarRef[]>([])
    const envVarsLoading = ref(false)
    const envVarSaving = ref(false)
    const deletingEnvKey = ref<string | null>(null)
    const latestSecretRef = ref<string | null>(null)

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

    function showSnackbar (text: string, color: 'success' | 'error' = 'success') {
        snackbar.text = text
        snackbar.color = color
        snackbar.show = true
    }

    async function loadEnvVarList () {
        envVarsLoading.value = true
        try {
            envVars.value = await getEnvVars()
        } catch (error) {
            console.error('Failed to load environment variables:', error)
            showSnackbar('加载环境变量失败', 'error')
        } finally {
            envVarsLoading.value = false
        }
    }

    async function ensureEnvVarsLoaded () {
        if (envVars.value.length || envVarsLoading.value) return
        await loadEnvVarList()
    }

    function openEnvVars () {
        currentView.value = 'env-vars'
        loadEnvVarList()
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

    async function saveEnvVar (payload?: { key: string, value: string }) {
        const key = payload?.key.trim() ?? ''
        const value = payload?.value.trim() ?? ''
        if (!key || !value || envVarSaving.value) return

        envVarSaving.value = true
        try {
            const saved = await upsertEnvVar({ key, value })
            latestSecretRef.value = saved.secret_ref
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

    async function copySecretRef (secretRef: string) {
        await copyText(secretRef, {
            onSuccess: () => showSnackbar('secret_ref 已复制'),
            onError: () => showSnackbar('复制 secret_ref 失败', 'error'),
        })
    }
</script>
