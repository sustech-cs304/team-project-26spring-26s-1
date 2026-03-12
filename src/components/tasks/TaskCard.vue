<template>
    <v-card variant="outlined" rounded="xl" class="pa-3" :color="cardBorderColor(task.status)"
        :style="cardStyle(task.status)">
        <!-- 第一行 -->
        <div class="d-flex align-start ga-3">
            <v-sheet :color="iconBgColor(task.status)" width="34" height="34" rounded="lg"
                class="d-flex align-center justify-center flex-shrink-0">
                <v-icon :size="16" :color="typeIconColor(task.type)">{{ typeIcon(task.type) }}</v-icon>
            </v-sheet>
            <div class="flex-grow-1 min-width-0">
                <div class="d-flex align-center ga-1 flex-wrap">
                    <span class="text-body-2 font-weight-bold text-truncate">{{ task.name }}</span>
                    <v-chip :color="statusColor(task.status)" variant="outlined" size="x-small" density="compact"
                        style="font-size:9px;height:18px;">
                        <span class="status-dot mr-1" :class="{ 'dot-running': task.status === 'running' }"
                            :style="task.status !== 'running' ? { background: statusColorRaw(task.status) } : {}" />
                        {{ task.status }}
                    </v-chip>
                    <v-chip variant="tonal" size="x-small" density="compact" style="font-size:9px;height:18px;">
                        {{ task.type }}
                    </v-chip>
                </div>
                <div v-if="task.description" class="text-caption text-medium-emphasis mt-1" style="line-height:1.5;">
                    {{ task.description }}
                </div>
            </div>
            <!-- 操作区 -->
            <div class="d-flex align-center ga-1 flex-shrink-0">
                <v-switch :model-value="task.status !== 'paused' && task.status !== 'failed'" density="compact"
                    hide-details color="success" style="transform:scale(0.75);transform-origin:right center;"
                    @change="emit('toggle', task)" />
                <v-menu location="bottom end">
                    <template #activator="{ props }">
                        <v-btn v-bind="props" icon variant="text" size="x-small" width="28" height="28">
                            <v-icon size="16">mdi-dots-horizontal</v-icon>
                        </v-btn>
                    </template>
                    <v-list density="compact" min-width="140">
                        <v-list-item v-if="task.status === 'running' || task.status === 'paused'"
                            @click="emit('pause', task)">
                            <template #prepend>
                                <v-icon size="14">{{ task.status === 'running' ? 'mdi-pause' : 'mdi-play' }}</v-icon>
                            </template>
                            <v-list-item-title class="text-caption">
                                {{ task.status === 'running' ? 'Pause' : 'Resume' }}
                            </v-list-item-title>
                        </v-list-item>
                        <v-list-item @click="emit('logs', task)">
                            <template #prepend><v-icon size="14">mdi-text-box-outline</v-icon></template>
                            <v-list-item-title class="text-caption">View Logs</v-list-item-title>
                        </v-list-item>
                        <v-list-item @click="emit('edit', task)">
                            <template #prepend><v-icon size="14">mdi-pencil</v-icon></template>
                            <v-list-item-title class="text-caption">Edit</v-list-item-title>
                        </v-list-item>
                        <v-divider />
                        <v-list-item @click="emit('delete', task)">
                            <template #prepend><v-icon size="14" color="error">mdi-delete</v-icon></template>
                            <v-list-item-title class="text-caption text-error">Delete</v-list-item-title>
                        </v-list-item>
                    </v-list>
                </v-menu>
            </div>
        </div>

        <!-- 第二行：元数据 -->
        <div class="d-flex flex-wrap align-center ga-1 mt-2" style="padding-left:48px;">
            <template v-if="task.type === 'recurring' && task.intervalLabel">
                <span class="d-inline-flex align-center ga-1">
                    <v-icon size="12" class="text-medium-emphasis">mdi-refresh</v-icon>
                    <span class="text-medium-emphasis" style="font-size:11px;">{{ task.intervalLabel }}</span>
                </span>
            </template>
            <template v-if="task.type === 'scheduled' && task.scheduledAt">
                <span class="d-inline-flex align-center ga-1">
                    <v-icon size="12" class="text-medium-emphasis">mdi-clock-outline</v-icon>
                    <span class="text-medium-emphasis" style="font-size:11px;">{{ task.scheduledAt }}</span>
                </span>
            </template>
            <template v-if="task.type === 'event-triggered' && task.eventSource">
                <span class="d-inline-flex align-center ga-1">
                    <v-icon size="12" class="text-medium-emphasis">mdi-lightning-bolt</v-icon>
                    <span class="text-medium-emphasis" style="font-size:11px;">{{ task.eventSource }}</span>
                </span>
            </template>
            <template v-if="task.type === 'monitor' && task.monitorTarget">
                <span class="d-inline-flex align-center ga-1">
                    <v-icon size="12" class="text-medium-emphasis">mdi-eye-outline</v-icon>
                    <span class="text-medium-emphasis" style="font-size:11px;">{{ task.monitorTarget }}</span>
                </span>
            </template>
            <template v-if="task.lastRunAt">
                <span class="d-inline-flex align-center ga-1">
                    <v-icon size="12" class="text-medium-emphasis">mdi-history</v-icon>
                    <span class="text-medium-emphasis" style="font-size:11px;">Last: {{ task.lastRunAt }}</span>
                </span>
            </template>
            <template v-if="task.nextRunAt">
                <span class="d-inline-flex align-center ga-1">
                    <v-icon size="12" class="text-medium-emphasis">mdi-timer-outline</v-icon>
                    <span class="text-medium-emphasis" style="font-size:11px;">Next: {{ task.nextRunAt }}</span>
                </span>
            </template>
            <template v-if="task.runCount != null">
                <span class="d-inline-flex align-center ga-1">
                    <v-icon size="12" class="text-medium-emphasis">mdi-pound</v-icon>
                    <span class="text-medium-emphasis" style="font-size:11px;">
                        {{ task.runCount }} runs{{ task.failCount ? ` / ${task.failCount} fails` : '' }}
                    </span>
                </span>
            </template>
            <template v-if="task.tags && task.tags.length">
                <v-chip v-for="tag in task.tags" :key="tag" variant="tonal" size="x-small" density="compact"
                    style="font-size:9px;height:16px;">{{ tag }}</v-chip>
            </template>
        </div>
    </v-card>
</template>

<script setup lang="ts">
    import type { Task, TaskStatus } from '@/utils/tasks'
    import { typeIcon, typeIconColor, statusColor, statusColorRaw } from '@/utils/tasks'

    defineProps<{ task: Task }>()
    const emit = defineEmits<{
        (e: 'edit', task: Task): void
        (e: 'delete', task: Task): void
        (e: 'pause', task: Task): void
        (e: 'toggle', task: Task): void
        (e: 'logs', task: Task): void
    }>()

    function cardBorderColor (status: TaskStatus) {
        if (status === 'running') return 'success'
        if (status === 'failed') return 'error'
        if (status === 'paused') return 'warning'
        return undefined
    }

    function cardStyle (status: TaskStatus) {
        if (status === 'completed') return { opacity: '0.6' }
        if (status === 'running') return { background: 'rgba(var(--v-theme-success), 0.03)' }
        if (status === 'failed') return { background: 'rgba(var(--v-theme-error), 0.03)' }
        return {}
    }

    function iconBgColor (status: TaskStatus) {
        if (status === 'running') return 'success-lighten-5'
        if (status === 'failed') return 'error-lighten-5'
        if (status === 'paused') return 'warning-lighten-5'
        return 'surface-variant'
    }
</script>

<style scoped>
    .status-dot {
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
</style>
