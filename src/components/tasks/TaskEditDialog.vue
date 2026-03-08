<template>
    <v-dialog :model-value="modelValue" max-width="512" scrollable
        @update:model-value="emit('update:modelValue', $event)">
        <v-card rounded="lg" class="border">
            <v-card-title class="d-flex align-center ga-2 px-4 pt-4 pb-2">
                <v-icon size="16" color="primary">{{ task ? 'mdi-pencil' : 'mdi-plus-circle' }}</v-icon>
                <span class="text-body-2 font-weight-bold">{{ task ? 'Edit Task' : 'Create New Task' }}</span>
            </v-card-title>
            <v-divider />
            <v-card-text class="pa-4" style="max-height:70vh;overflow-y:auto;">
                <div class="d-flex flex-column ga-4">
                    <!-- Task Type -->
                    <div>
                        <div class="text-caption text-medium-emphasis mb-2">Task Type</div>
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                            <div v-for="t in taskTypes" :key="t.value" class="type-option"
                                :class="{ 'type-option--active': form.type === t.value }"
                                @click="form.type = t.value as TaskType">
                                <v-icon :size="16" :color="form.type === t.value ? 'primary' : undefined">{{ t.icon
                                }}</v-icon>
                                <div>
                                    <div class="text-caption font-weight-bold"
                                        :class="form.type === t.value ? 'text-primary' : ''">{{ t.label }}</div>
                                    <div class="text-medium-emphasis" style="font-size:10px;">{{ t.desc }}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <!-- Name -->
                    <div>
                        <div class="text-caption text-medium-emphasis mb-1">Task Name</div>
                        <v-text-field v-model="form.name" density="compact" variant="outlined"
                            placeholder="e.g. Library Seat Monitor" hide-details />
                    </div>
                    <!-- Description -->
                    <div>
                        <div class="text-caption text-medium-emphasis mb-1">Description</div>
                        <v-textarea v-model="form.description" density="compact" variant="outlined"
                            placeholder="Describe what this task does..." hide-details :rows="3" no-resize />
                    </div>
                    <!-- Type-specific config -->
                    <div class="type-config-block">
                        <div class="text-caption font-weight-bold text-medium-emphasis mb-2"
                            style="font-size:10px;letter-spacing:0.08em;text-transform:uppercase;">
                            {{ form.type }} Configuration
                        </div>
                        <template v-if="form.type === 'recurring'">
                            <div class="text-caption text-medium-emphasis mb-1">Cron Expression</div>
                            <v-text-field v-model="form.cron" density="compact" variant="outlined"
                                placeholder="0 9 * * *" hide-details class="mb-3"
                                style="font-family:monospace;font-size:12px;" />
                            <div class="text-caption text-medium-emphasis mb-1">Readable Description</div>
                            <v-text-field v-model="form.intervalLabel" density="compact" variant="outlined"
                                placeholder="Every day at 09:00" hide-details />
                        </template>
                        <template v-else-if="form.type === 'scheduled'">
                            <div class="text-caption text-medium-emphasis mb-1">Execute At</div>
                            <v-text-field v-model="form.scheduledAt" type="datetime-local" density="compact"
                                variant="outlined" hide-details />
                        </template>
                        <template v-else-if="form.type === 'event-triggered'">
                            <div class="text-caption text-medium-emphasis mb-1">Event Source</div>
                            <v-select v-model="form.eventSource" density="compact" variant="outlined"
                                :items="eventSources" hide-details class="mb-3" />
                            <div class="text-caption text-medium-emphasis mb-1">Trigger Condition</div>
                            <v-text-field v-model="form.triggerCondition" density="compact" variant="outlined"
                                placeholder="e.g. New email received" hide-details />
                        </template>
                        <template v-else-if="form.type === 'monitor'">
                            <div class="text-caption text-medium-emphasis mb-1">Monitor Target</div>
                            <v-text-field v-model="form.monitorTarget" density="compact" variant="outlined"
                                placeholder="e.g. Library Floor 3 Area A" hide-details class="mb-3" />
                            <div class="text-caption text-medium-emphasis mb-1">Poll Interval</div>
                            <v-select v-model="form.pollInterval" density="compact" variant="outlined"
                                :items="pollIntervals" hide-details />
                        </template>
                    </div>
                    <!-- Tags -->
                    <div>
                        <div class="text-caption text-medium-emphasis mb-2">Tags</div>
                        <div class="d-flex flex-wrap align-center ga-1">
                            <v-chip v-for="(tag, i) in form.tags" :key="tag" variant="tonal" size="x-small" closable
                                style="font-size:10px;" @click:close="form.tags.splice(i, 1)">{{ tag }}</v-chip>
                            <input v-model="tagInput" class="tag-input" placeholder="Add tag..."
                                @keydown.enter.prevent="addTag" />
                        </div>
                    </div>
                </div>
            </v-card-text>
            <v-divider />
            <v-card-actions class="px-4 py-3 ga-2 justify-end">
                <v-btn variant="outlined" size="small" @click="emit('update:modelValue', false)">Cancel</v-btn>
                <v-btn color="primary" size="small" :disabled="!form.name.trim()" @click="submit">
                    {{ task ? 'Save Changes' : 'Create Task' }}
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script setup lang="ts">
    import type { Task, TaskForm, TaskType } from '@/utils/tasks'
    import { makeEmptyForm, taskToForm } from '@/utils/tasks'

    const props = defineProps<{ modelValue: boolean; task?: Task | null }>()
    const emit = defineEmits<{
        (e: 'update:modelValue', v: boolean): void
        (e: 'submit', form: TaskForm): void
    }>()

    const taskTypes = [
        { value: 'recurring', icon: 'mdi-refresh', label: 'Recurring', desc: 'Runs on a schedule' },
        { value: 'scheduled', icon: 'mdi-clock-outline', label: 'Scheduled', desc: 'Runs once at a time' },
        { value: 'event-triggered', icon: 'mdi-lightning-bolt', label: 'Event', desc: 'Triggered by events' },
        { value: 'monitor', icon: 'mdi-eye-outline', label: 'Monitor', desc: 'Watches for changes' },
    ]
    const eventSources = ['Email Inbox', 'Blackboard', 'Course System', 'Calendar', 'File System', 'Webhook']
    const pollIntervals = ['1 min', '2 min', '5 min', '15 min', '30 min', '1 hr']

    const form = ref<TaskForm>(makeEmptyForm())
    const tagInput = ref('')

    watch(() => props.modelValue, (v) => {
        if (v) {
            form.value = props.task ? taskToForm(props.task) : makeEmptyForm()
            tagInput.value = ''
        }
    })

    const addTag = () => {
        const t = tagInput.value.trim()
        if (t && !form.value.tags.includes(t)) form.value.tags.push(t)
        tagInput.value = ''
    }

    const submit = () => {
        if (!form.value.name.trim()) return
        emit('submit', { ...form.value, tags: [...form.value.tags] })
        emit('update:modelValue', false)
    }
</script>

<style scoped>
    .type-option {
        display: flex;
        align-items: center;
        gap: 10px;
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        border-radius: 8px;
        padding: 10px 12px;
        cursor: pointer;
        transition: border-color 0.15s, background 0.15s;
    }

    .type-option:hover {
        border-color: rgba(var(--v-theme-on-surface), 0.3);
    }

    .type-option--active {
        border-color: rgba(var(--v-theme-primary), 0.5);
        background: rgba(var(--v-theme-primary), 0.1);
    }

    .type-config-block {
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        border-radius: 8px;
        background: rgba(var(--v-theme-surface), 0.5);
        padding: 12px;
    }

    .tag-input {
        height: 26px;
        width: 90px;
        font-size: 12px;
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        border-radius: 6px;
        padding: 0 8px;
        background: transparent;
        color: inherit;
        outline: none;
    }

    .tag-input:focus {
        border-color: rgb(var(--v-theme-primary));
    }
</style>
