<template>
    <v-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" max-width="480"
        persistent>
        <v-card rounded="lg">
            <v-card-title class="d-flex align-center justify-space-between px-4 pt-4 pb-2">
                <div class="d-flex align-center ga-2">
                    <v-icon size="16" color="primary">mdi-calendar-edit</v-icon>
                    <span class="text-body-2 font-weight-bold">{{ event ? 'Edit Event' : 'New Event' }}</span>
                </div>
                <v-btn icon size="x-small" variant="text" @click="$emit('update:modelValue', false)">
                    <v-icon size="14">mdi-close</v-icon>
                </v-btn>
            </v-card-title>

            <v-divider />

            <v-card-text class="px-4 py-4">
                <div class="d-flex flex-column ga-3">
                    <v-text-field v-model="form.title" label="Title" density="compact" variant="outlined"
                        placeholder="Event title" hide-details autofocus />

                    <!-- 类型选择 -->
                    <div>
                        <div class="text-caption text-medium-emphasis mb-2">Type</div>
                        <div class="d-flex flex-wrap ga-1">
                            <button v-for="t in eventTypes" :key="t.value" class="type-chip"
                                :class="{ active: form.type === t.value }"
                                :style="form.type === t.value ? { background: `rgba(var(--v-theme-${t.color}),0.15)`, color: `rgb(var(--v-theme-${t.color}))` } : {}"
                                @click="form.type = t.value">
                                <v-icon :size="11" class="mr-1">{{ t.icon }}</v-icon>{{ t.label }}
                            </button>
                        </div>
                    </div>

                    <!-- 日期 -->
                    <div class="d-flex ga-2">
                        <v-text-field v-model="form.date" label="Date" density="compact" variant="outlined" type="date"
                            hide-details />
                        <v-text-field v-model="form.time" label="Time (optional)" density="compact" variant="outlined"
                            type="time" hide-details />
                    </div>

                    <!-- 多天范围 -->
                    <v-text-field v-model="form.endDate" label="End Date (optional)" density="compact"
                        variant="outlined" type="date" hide-details />

                    <v-textarea v-model="form.description" label="Description (optional)" density="compact"
                        variant="outlined" rows="2" hide-details auto-grow />

                    <v-text-field v-model="form.location" label="Location (optional)" density="compact"
                        variant="outlined" hide-details />
                </div>
            </v-card-text>

            <v-divider />

            <v-card-actions class="px-4 py-3 ga-2 justify-end">
                <v-btn variant="outlined" size="small" @click="$emit('update:modelValue', false)">Cancel</v-btn>
                <v-btn color="primary" size="small" :disabled="!form.title.trim() || !form.date" @click="submit">
                    {{ event ? 'Save Changes' : 'Create Event' }}
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script setup lang="ts">
    import type { CalEvent, EventType } from '@/utils/calendar'
    import { EVENT_TYPE_ICON, EVENT_TYPE_COLOR } from '@/utils/calendar'

    interface EventForm {
        title: string
        type: EventType
        date: string
        time: string
        endDate: string
        description: string
        location: string
    }

    const props = defineProps<{
        modelValue: boolean
        event?: CalEvent | null
        defaultDate?: string
    }>()

    const emit = defineEmits<{
        'update:modelValue': [v: boolean]
        submit: [form: EventForm]
    }>()

    const eventTypes: { value: EventType; label: string; icon: string; color: string }[] = [
        { value: 'class', label: 'Class', icon: EVENT_TYPE_ICON.class, color: 'primary' },
        { value: 'exam', label: 'Exam', icon: EVENT_TYPE_ICON.exam, color: 'error' },
        { value: 'deadline', label: 'Deadline', icon: EVENT_TYPE_ICON.deadline, color: 'warning' },
        { value: 'personal', label: 'Personal', icon: EVENT_TYPE_ICON.personal, color: 'info' },
        { value: 'meeting', label: 'Meeting', icon: EVENT_TYPE_ICON.meeting, color: 'secondary' },
    ]

    const makeEmpty = (): EventForm => ({
        title: '', type: 'personal', date: props.defaultDate ?? '', time: '',
        endDate: '', description: '', location: '',
    })

    const form = ref<EventForm>(makeEmpty())

    watch(() => props.modelValue, open => {
        if (open) {
            if (props.event) {
                form.value = {
                    title: props.event.title,
                    type: props.event.type,
                    date: props.event.date,
                    time: props.event.time ?? '',
                    endDate: props.event.endDate ?? '',
                    description: props.event.description ?? '',
                    location: props.event.location ?? '',
                }
            } else {
                form.value = makeEmpty()
            }
        }
    })

    const submit = () => {
        if (!form.value.title.trim() || !form.value.date) return
        emit('submit', { ...form.value })
        emit('update:modelValue', false)
    }
</script>

<style scoped>
    .type-chip {
        display: inline-flex;
        align-items: center;
        padding: 3px 9px;
        font-size: 11px;
        font-weight: 500;
        border-radius: 6px;
        border: none;
        cursor: pointer;
        transition: background 0.15s, color 0.15s;
        color: rgba(var(--v-theme-on-surface), 0.6);
        background: rgba(var(--v-theme-surface-variant), 0.3);
    }

    .type-chip:hover {
        opacity: 0.85;
    }

    .type-chip.active {
        font-weight: 600;
    }
</style>
