<template>
    <!-- 日志/详情抽屉 -->
    <v-dialog :model-value="modelValue" max-width="480" @update:model-value="emit('update:modelValue', $event)">
        <v-card v-if="task" rounded="lg">
            <v-card-title class="d-flex align-center ga-2 px-4 pt-4 pb-2">
                <v-icon size="16" color="primary">mdi-text-box-outline</v-icon>
                <span class="text-body-2 font-weight-bold">{{ task.name }} — Logs</span>
                <v-spacer />
                <v-chip :color="statusColor(task.status)" variant="outlined" size="x-small" density="compact"
                    style="font-size:9px;">{{ task.status }}</v-chip>
            </v-card-title>
            <v-divider />

            <!-- 统计行 -->
            <div class="d-flex ga-4 px-4 py-3 border-b">
                <div class="text-center">
                    <div class="text-subtitle-2 font-weight-bold">{{ task.runCount ?? 0 }}</div>
                    <div class="text-caption text-medium-emphasis">Runs</div>
                </div>
                <v-divider vertical style="height:36px;" />
                <div class="text-center">
                    <div class="text-subtitle-2 font-weight-bold text-error">{{ task.failCount ?? 0 }}</div>
                    <div class="text-caption text-medium-emphasis">Fails</div>
                </div>
                <v-divider vertical style="height:36px;" />
                <div class="text-center">
                    <div class="text-subtitle-2 font-weight-bold">{{ task.lastRunAt ?? '—' }}</div>
                    <div class="text-caption text-medium-emphasis">Last Run</div>
                </div>
            </div>

            <!-- 日志列表 -->
            <v-card-text class="pa-0" style="max-height:300px;overflow-y:auto;">
                <div v-if="!task.logs || task.logs.length === 0"
                    class="d-flex flex-column align-center justify-center py-8">
                    <v-icon size="28" class="text-medium-emphasis mb-2"
                        style="opacity:0.4;">mdi-text-box-outline</v-icon>
                    <span class="text-caption text-medium-emphasis">No logs yet</span>
                </div>
                <div v-else class="pa-3 d-flex flex-column ga-1">
                    <div v-for="(log, i) in task.logs" :key="i" class="d-flex align-start ga-2 log-row pa-2 rounded">
                        <v-icon :size="13" :color="logColor(log.level)" class="mt-px flex-shrink-0">
                            {{ logIcon(log.level) }}
                        </v-icon>
                        <div class="flex-grow-1 min-width-0">
                            <span class="text-medium-emphasis mr-2" style="font-size:10px;font-family:monospace;">
                                {{ log.time }}
                            </span>
                            <span style="font-size:11px;">{{ log.message }}</span>
                        </div>
                    </div>
                </div>
            </v-card-text>
            <v-divider />
            <v-card-actions class="px-4 py-3 justify-end">
                <v-btn size="small" variant="outlined" @click="emit('update:modelValue', false)">Close</v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script setup lang="ts">
    import type { Task } from '@/utils/tasks'
    import { statusColor } from '@/utils/tasks'

    defineProps<{ modelValue: boolean; task?: Task | null }>()
    const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()

    const logColor = (level: string) =>
        ({ info: 'medium-emphasis', warn: 'warning', error: 'error' }[level] ?? 'medium-emphasis')
    const logIcon = (level: string) =>
        ({ info: 'mdi-information-outline', warn: 'mdi-alert-outline', error: 'mdi-close-circle-outline' }[level] ?? 'mdi-information-outline')
</script>

<style scoped>
    .log-row:hover {
        background: rgba(var(--v-theme-surface-variant), 0.4);
    }
</style>
