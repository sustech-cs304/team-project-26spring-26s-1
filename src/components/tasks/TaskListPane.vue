<template>
    <div>
        <div v-if="showStatusFilters" class="px-2 pt-2 pb-1">
            <v-btn-toggle :model-value="statusFilter" mandatory density="compact" rounded="lg" divided
                variant="tonal" class="w-100"
                @update:model-value="emit('update:statusFilter', String($event ?? 'all'))">
                <v-btn v-for="item in statusFilters" :key="item.value" :value="item.value"
                    class="text-none flex-grow-1 px-1" size="x-small" min-width="0" :ripple="false">
                    {{ item.label }}
                </v-btn>
            </v-btn-toggle>
        </div>

        <v-divider v-if="showStatusFilters" class="mx-2" />

        <div v-if="loading" class="d-flex justify-center py-4">
            <v-progress-circular indeterminate size="24" color="primary" />
        </div>

        <v-list v-else-if="tasks.length" nav density="compact" bg-color="transparent" class="py-1">
            <v-list-item v-for="task in tasks" :key="task.id" :active="selectedTaskId === task.id" rounded="lg"
                active-class="theme-active-list-item" slim prepend-gap="8" :ripple="false" class="px-2 py-1 mb-1"
                @click="emit('select', task.id)" @contextmenu.prevent.stop="openTaskMenu(task.id)">
                <template #prepend>
                    <v-icon size="16">{{ MODE_ICON[task.execution_mode] }}</v-icon>
                </template>
                <v-list-item-title class="text-body-2 font-weight-medium">{{ task.name }}</v-list-item-title>
                <v-list-item-subtitle class="text-caption text-medium-emphasis">
                    {{ task.last_run_at ? formatRelativeRun(task.last_run_at) : '暂无运行记录' }}
                </v-list-item-subtitle>
                <template #append>
                    <v-menu :model-value="taskMenuId === task.id" :close-on-content-click="true" location="end"
                        @update:model-value="updateTaskMenu(task.id, $event)">
                        <template #activator="{ props: menuProps }">
                            <v-btn v-bind="menuProps" icon="mdi-dots-vertical" size="x-small" variant="text"
                                :ripple="false" class="task-menu-btn" @click.prevent.stop />
                        </template>
                        <v-list density="compact" min-width="132" nav slim tile>
                            <v-list-item title="编辑" slim density="compact" @click="emit('edit', task.id)">
                                <template #prepend>
                                    <v-icon size="x-small">mdi-pencil-outline</v-icon>
                                </template>
                            </v-list-item>
                            <v-list-item title="复制" slim density="compact" @click="emit('duplicate', task.id)">
                                <template #prepend>
                                    <v-icon size="x-small">mdi-content-copy</v-icon>
                                </template>
                            </v-list-item>
                            <v-list-item slim density="compact" :title="task.status === 'disabled' ? '启用' : '禁用'"
                                @click="emit('toggle-status', task.id)">
                                <template #prepend>
                                    <v-icon size="x-small">
                                        {{ task.status === 'disabled' ? 'mdi-play-circle-outline' : 'mdi-pause-circle-outline' }}
                                    </v-icon>
                                </template>
                            </v-list-item>
                            <v-divider />
                            <v-list-item slim density="compact" title="删除" base-color="error"
                                @click="emit('delete', task.id)">
                                <template #prepend>
                                    <v-icon size="x-small">mdi-delete-outline</v-icon>
                                </template>
                            </v-list-item>
                        </v-list>
                    </v-menu>
                </template>
            </v-list-item>
        </v-list>

        <div v-else class="text-center py-4 text-body-2 text-medium-emphasis">
            {{ emptyText }}
        </div>
    </div>
</template>

<script setup lang="ts">
    import type { Task } from '@/utils/tasks'
    import { MODE_ICON, formatDateTime, parseTaskDateTime } from '@/utils/tasks'

    const props = defineProps<{
        loading: boolean
        searchMode: boolean
        search: string
        statusFilter: string
        statusFilters: readonly { label: string, value: string }[]
        tasks: Task[]
        selectedTaskId: string | null
    }>()

    const emit = defineEmits<{
        'update:statusFilter': [value: string]
        select: [taskId: string]
        edit: [taskId: string]
        duplicate: [taskId: string]
        'toggle-status': [taskId: string]
        delete: [taskId: string]
    }>()

    const hasSearchKeyword = computed(() => props.search.trim().length > 0)
    const taskMenuId = ref<string | null>(null)
    const showStatusFilters = computed(() => props.searchMode && hasSearchKeyword.value)
    const emptyText = computed(() => {
        if (!props.searchMode) return '暂无任务'
        return hasSearchKeyword.value ? '未找到相关任务' : '输入关键词搜索任务'
    })

    function formatRelativeRun (value: string) {
        const date = parseTaskDateTime(value)
        if (!date) return formatDateTime(value)

        const diff = Date.now() - date.getTime()
        const hours = Math.floor(diff / 3_600_000)
        const days = Math.floor(diff / 86_400_000)

        if (days > 0) return `${days}d ago`
        if (hours > 0) return `${hours}h ago`
        const minutes = Math.max(1, Math.floor(diff / 60_000))
        return `${minutes}m ago`
    }

    function openTaskMenu (taskId: string) {
        emit('select', taskId)
        taskMenuId.value = taskId
    }

    function updateTaskMenu (taskId: string, opened: boolean) {
        taskMenuId.value = opened ? taskId : null
    }
</script>

<style scoped>
    .task-menu-btn {
        opacity: 0;
    }

    :deep(.v-list-item:hover) .task-menu-btn,
    .task-menu-btn:focus-visible,
    .task-menu-btn[aria-expanded="true"] {
        opacity: 1;
    }
</style>
