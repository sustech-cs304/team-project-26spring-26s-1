<template>
    <v-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" max-width="520"
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

                    <div class="d-flex ga-2">
                        <v-select v-model="form.source" :items="sourceItems" label="Source" density="compact"
                            variant="outlined" hide-details />
                        <v-text-field v-model="form.color" label="Color" density="compact" variant="outlined" type="color"
                            hide-details />
                    </div>

                    <div class="d-flex ga-2">
                        <v-text-field v-model="form.date" label="Date" density="compact" variant="outlined" type="date"
                            hide-details />
                        <v-text-field v-model="form.startTime" label="Start Time (optional)" density="compact" variant="outlined"
                            type="time" hide-details />
                        <v-text-field v-model="form.endTime" label="End Time (optional)" density="compact" variant="outlined"
                            type="time" hide-details />
                    </div>

                    <v-text-field v-model="form.endDate" label="End Date (optional)" density="compact"
                        variant="outlined" type="date" hide-details />

                    <v-textarea v-model="form.description" label="Description (optional)" density="compact"
                        variant="outlined" rows="2" hide-details auto-grow />

                    <v-text-field v-model="form.location" label="Location (optional)" density="compact"
                        variant="outlined" hide-details />

                    <v-text-field v-model="form.link" label="Link (optional)" density="compact"
                        variant="outlined" hide-details placeholder="https://..." />
                </div>
            </v-card-text>

            <v-divider />

            <v-card-actions class="px-4 py-3 ga-2 justify-end">
                <v-btn variant="outlined" size="small" @click="$emit('update:modelValue', false)">Cancel</v-btn>
                <v-btn color="primary" size="small" :disabled="!canSubmit" @click="submit">
                    {{ event ? 'Save Changes' : 'Create Event' }}
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script setup lang="ts">
    import type { CalEvent, EventType } from '@/utils/calendar'
    import {
        EVENT_TYPE_ICON,
        EVENT_TYPE_COLOR,
        EVENT_SOURCES,
        eventSourceRawColor,
    } from '@/utils/calendar'

    interface EventForm {
        title: string
        type: EventType
        source: CalEvent['source']
        color: string
        date: string
        time: string
        startTime: string
        endTime: string
        endDate: string
        description: string
        location: string
        link: string
    }

    const props = defineProps<{
        modelValue: boolean
        event?: CalEvent | null
        defaultDate?: string
        sourceItems?: { title: string; value: string }[]
    }>()

    const emit = defineEmits<{
        'update:modelValue': [v: boolean]
        submit: [form: Omit<CalEvent, 'id'>]
    }>()

    const eventTypes: { value: EventType; label: string; icon: string; color: string }[] = [
        { value: 'class', label: 'Class', icon: EVENT_TYPE_ICON.class, color: EVENT_TYPE_COLOR.class },
        { value: 'exam', label: 'Exam', icon: EVENT_TYPE_ICON.exam, color: EVENT_TYPE_COLOR.exam },
        { value: 'deadline', label: 'Deadline', icon: EVENT_TYPE_ICON.deadline, color: EVENT_TYPE_COLOR.deadline },
        { value: 'personal', label: 'Personal', icon: EVENT_TYPE_ICON.personal, color: EVENT_TYPE_COLOR.personal },
        { value: 'meeting', label: 'Meeting', icon: EVENT_TYPE_ICON.meeting, color: EVENT_TYPE_COLOR.meeting },
    ]

    const fallbackSourceItems = EVENT_SOURCES.map(s => ({ title: s.label, value: s.value }))
    const sourceItems = computed(() => props.sourceItems && props.sourceItems.length > 0 ? props.sourceItems : fallbackSourceItems)

    const makeEmpty = (): EventForm => ({
        title: '',
        type: 'personal',
        source: 'life',
        color: eventSourceRawColor('life'),
        date: props.defaultDate ?? '',
        time: '',
        startTime: '',
        endTime: '',
        endDate: '',
        description: '',
        location: '',
        link: '',
    })

    const form = ref<EventForm>(makeEmpty())

    const canSubmit = computed(() => !!form.value.title.trim() && !!form.value.date && !!form.value.source)

    watch(() => props.modelValue, open => {
        if (!open) return
        if (props.event) {
            form.value = {
                title: props.event.title,
                type: props.event.type,
                source: props.event.source,
                color: props.event.color || eventSourceRawColor(props.event.source),
                date: props.event.date,
                time: props.event.time ?? '',
                startTime: props.event.startTime ?? props.event.time ?? '',
                endTime: props.event.endTime ?? '',
                endDate: props.event.endDate ?? '',
                description: props.event.description ?? '',
                location: props.event.location ?? '',
                link: props.event.link ?? '',
            }
            return
        }
        form.value = makeEmpty()
    })

    const submit = () => {
        if (!canSubmit.value) return
        emit('submit', {
            title: form.value.title,
            type: form.value.type,
            source: form.value.source,
            color: form.value.color,
            date: form.value.date,
            time: form.value.startTime || form.value.time || '',
            startTime: form.value.startTime || undefined,
            endTime: form.value.endTime || undefined,
            endDate: form.value.endDate || undefined,
            description: form.value.description || undefined,
            location: form.value.location || undefined,
            link: form.value.link || undefined,
        })
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
