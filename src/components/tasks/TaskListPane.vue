<template>
    <v-card rounded="lg" elevation="0" border>
        <v-card-text class="pb-2">
            <v-text-field
                :model-value="search"
                variant="solo-filled"
                flat
                hide-details
                rounded="lg"
                density="compact"
                prepend-inner-icon="mdi-magnify"
                placeholder="Search tasks"
                @update:model-value="emit('update:search', String($event ?? ''))"
            />
            <v-chip-group
                :model-value="statusFilter"
                selected-class="text-primary"
                class="mt-3"
                mandatory
                @update:model-value="emit('update:statusFilter', $event)"
            >
                <v-chip
                    v-for="item in statusFilters"
                    :key="item.value"
                    :value="item.value"
                    rounded="lg"
                    filter
                    variant="text"
                    size="small"
                >
                    {{ item.label }}
                </v-chip>
            </v-chip-group>
        </v-card-text>

        <v-divider />

        <v-progress-linear v-if="loading" indeterminate />

        <v-list v-else-if="tasks.length" lines="two" class="py-1">
            <v-list-item
                v-for="task in tasks"
                :key="task.id"
                :active="selectedTaskId === task.id"
                rounded="lg"
                class="mx-2 mb-1"
                @click="emit('select', task.id)"
            >
                <template #prepend>
                    <v-avatar size="32" rounded="lg" color="surface-variant">
                        <v-icon size="16">{{ MODE_ICON[task.execution_mode] }}</v-icon>
                    </v-avatar>
                </template>
                <v-list-item-title class="font-weight-medium text-body-2">{{ task.name }}</v-list-item-title>
                <v-list-item-subtitle class="text-caption">
                    {{ task.cron_expression ? cronToHuman(task.cron_expression) : 'Manual only' }}
                </v-list-item-subtitle>
                <template #append>
                    <div class="d-flex flex-column align-end ga-1">
                        <v-chip :color="TASK_STATUS_COLOR[task.status]" size="x-small" variant="tonal">
                            {{ task.status }}
                        </v-chip>
                        <span class="text-caption text-medium-emphasis">
                            {{ task.last_run_at ? formatRelativeRun(task.last_run_at) : 'No runs' }}
                        </span>
                    </div>
                </template>
            </v-list-item>
        </v-list>

        <v-empty-state v-else icon="mdi-format-list-checks" text="No tasks found" title="" />
    </v-card>
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

    function formatRelativeRun(value: string) {
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
