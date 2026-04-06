<template>
    <div>
        <div class="px-2 pt-1">
            <v-text-field :model-value="search" variant="solo-filled" flat hide-details rounded="lg" density="compact"
                prepend-inner-icon="mdi-magnify" placeholder="搜索任务"
                @update:model-value="emit('update:search', String($event ?? ''))" />
            <v-chip-group :model-value="statusFilter" selected-class="text-primary"
                @update:model-value="emit('update:statusFilter', $event)">
                <v-chip v-for="item in statusFilters" :key="item.value" :value="item.value" rounded="lg" filter
                    variant="text" size="small">
                    {{ item.label }}
                </v-chip>
            </v-chip-group>
        </div>

        <v-divider />

        <div v-if="loading" class="d-flex justify-center py-4">
            <v-progress-circular indeterminate size="24" color="primary" />
        </div>

        <v-list v-else-if="tasks.length" nav density="compact" class="py-1">
            <v-list-item v-for="task in tasks" :key="task.id" :active="selectedTaskId === task.id" rounded="lg"
                color="primary" slim prepend-gap="10" :ripple="false" class="task-item"
                @click="emit('select', task.id)">
                <template #prepend>
                    <v-icon size="small">{{ MODE_ICON[task.execution_mode] }}</v-icon>
                </template>
                <v-list-item-title class="task-item__title">{{ task.name }}</v-list-item-title>
                <v-list-item-subtitle class="task-item__subtitle">
                    {{ task.last_run_at ? formatRelativeRun(task.last_run_at) : '暂无运行记录' }}
                </v-list-item-subtitle>
                <template #append>
                    <v-chip :color="TASK_STATUS_COLOR[task.status]" size="x-small" variant="tonal">
                        {{ task.status }}
                    </v-chip>
                </template>
            </v-list-item>
        </v-list>

        <div v-else class="text-center py-4 text-body-medium opacity-70">
            暂无任务
        </div>
    </div>
</template>

<script setup lang="ts">
    import type { Task } from '@/utils/tasks'
    import { cronToHuman, MODE_ICON, TASK_STATUS_COLOR, formatDateTime } from '@/utils/tasks'

    defineProps<{
        loading: boolean
        search: string
        statusFilter: string
        statusFilters: readonly { label: string, value: string }[]
        tasks: Task[]
        selectedTaskId: string | null
    }>()

    const emit = defineEmits<{
        'update:search': [value: string]
        'update:statusFilter': [value: string]
        select: [taskId: string]
    }>()

    function formatRelativeRun (value: string) {
        const date = new Date(value)
        if (Number.isNaN(date.getTime())) return formatDateTime(value)

        const diff = Date.now() - date.getTime()
        const hours = Math.floor(diff / 3_600_000)
        const days = Math.floor(diff / 86_400_000)

        if (days > 0) return `${days}d ago`
        if (hours > 0) return `${hours}h ago`
        const minutes = Math.max(1, Math.floor(diff / 60_000))
        return `${minutes}m ago`
    }
</script>

<style scoped>
    .task-item__title {
        font-size: 0.92rem;
        font-weight: 500;
    }

    .task-item__subtitle {
        font-size: 0.78rem;
        margin-top: 2px;
    }
</style>
