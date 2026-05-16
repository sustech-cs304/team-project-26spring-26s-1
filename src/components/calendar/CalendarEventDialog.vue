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

                    <div class="d-flex ga-2 align-center">
                        <v-text-field v-model="form.title" label="Title" density="compact" variant="outlined"
                            placeholder="Event title" hide-details autofocus class="flex-grow-1" />
                        <v-menu v-model="colorMenuOpen" :close-on-content-click="false" location="bottom end">
                            <template #activator="{ props: menuProps }">
                                <v-btn type="button" v-bind="menuProps" variant="outlined" height="40" min-width="92"
                                    class="px-2 text-none d-flex align-center justify-space-between">
                                    <span class="calendar-dialog-muted-text">Color</span>
                                    <v-sheet width="18" height="18" rounded="sm" border class="ms-2"
                                        :style="{ backgroundColor: form.color }" />
                                </v-btn>
                            </template>

                            <v-card rounded="lg" class="pa-2" width="180">
                                <v-list density="compact" bg-color="transparent" class="pa-0">
                                    <v-list-item v-for="option in calendarColorOptions" :key="option.hex" rounded="lg"
                                        slim @click="confirmColor(option.hex)">
                                        <template #prepend>
                                            <v-sheet width="14" height="14" rounded="sm"
                                                :style="{ background: option.hex }" />
                                        </template>
                                        <v-list-item-title class="text-caption">{{ option.label }}</v-list-item-title>
                                        <template v-if="form.color === option.hex" #append>
                                            <v-icon size="14">mdi-check</v-icon>
                                        </template>
                                    </v-list-item>
                                </v-list>
                            </v-card>
                        </v-menu>
                    </div>



                    <div class="d-flex ga-2">
                        <v-text-field v-model="form.date" label="Date" density="compact" variant="outlined" type="date"
                            hide-details />
                        <v-text-field v-model="form.startTime" label="Start Time (optional)" density="compact"
                            variant="outlined" type="time" hide-details />
                        <v-text-field v-model="form.endTime" label="End Time (optional)" density="compact"
                            variant="outlined" type="time" hide-details />
                    </div>

                    <div v-if="!isTimeRangeValid" class="d-flex">
                        <v-chip color="error" variant="tonal" size="small" class="mt-1">End time must be later than
                            start time</v-chip>
                    </div>

                    <v-textarea v-model="form.description" label="Description (optional)" density="compact"
                        variant="outlined" rows="2" hide-details auto-grow />

                    <v-text-field v-model="form.location" label="Location (optional)" density="compact"
                        variant="outlined" hide-details />

                    <v-text-field v-model="form.link" label="Link (optional)" density="compact" variant="outlined"
                        hide-details placeholder="https://..." />
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
    import type { CalEvent } from '@/types/calendar'
    import { CALENDAR_COLOR_OPTIONS, normalizeCalendarColor } from '@/utils/calendarColors'

    interface EventForm {
        title: string
        color: string
        date: string
        startTime: string
        endTime: string
        description: string
        location: string
        link: string
    }

    const props = defineProps<{
        modelValue: boolean
        event?: CalEvent | null
        defaultDate?: string
        defaultColor?: string
    }>()

    const emit = defineEmits<{
        'update:modelValue': [v: boolean]
        submit: [form: Omit<CalEvent, 'id'>]
    }>()

    const makeEmpty = (): EventForm => ({
        title: '',
        color: normalizeCalendarColor(props.defaultColor, '#4ca8df'),
        date: props.defaultDate ?? '',
        startTime: '12:00',
        endTime: '12:00',
        description: '',
        location: '',
        link: '',
    })

    const form = ref<EventForm>(makeEmpty())
    const colorMenuOpen = ref(false)
    const calendarColorOptions = CALENDAR_COLOR_OPTIONS

    const parseTimeToMinutes = (time: string): number | null => {
        if (!time) return null
        const parts = time.split(':')
        if (parts.length !== 2) return null
        const h = Number(parts[0])
        const m = Number(parts[1])
        if (!Number.isFinite(h) || !Number.isFinite(m)) return null
        return h * 60 + m
    }

    const isTimeRangeValid = computed(() => {
        const start = parseTimeToMinutes(form.value.startTime)
        const end = parseTimeToMinutes(form.value.endTime)
        if (start === null || end === null) return true
        return end >= start
    })

    const canSubmit = computed(() => (
        !!form.value.title.trim()
        && !!form.value.date
        && isTimeRangeValid.value
    ))



    watch(() => props.modelValue, open => {
        if (!open) return
        if (props.event) {
            form.value = {
                title: props.event.title,
                color: normalizeCalendarColor(props.event.color, '#4ca8df'),
                date: props.event.date,
                startTime: props.event.startTime || '12:00',
                endTime: props.event.endTime || props.event.startTime || '12:00',
                description: props.event.description ?? '',
                location: props.event.location ?? '',
                link: props.event.link ?? '',
            }
        } else {
            // 新建时强制重置所有字段，endTime与startTime同步，避免校验残留
            const empty = makeEmpty()
            empty.endTime = empty.startTime
            form.value = { ...empty }
        }
        form.value.color = normalizeCalendarColor(form.value.color)
        colorMenuOpen.value = false
    })

    const confirmColor = (color: string) => {
        form.value.color = normalizeCalendarColor(color)
        colorMenuOpen.value = false
    }

    const submit = () => {
        if (!canSubmit.value) return
        emit('submit', {
            title: form.value.title,
            source: 'user',
            color: form.value.color,
            date: form.value.date,
            time: form.value.startTime || '',
            startTime: form.value.startTime || undefined,
            endTime: form.value.endTime || undefined,
            description: form.value.description || undefined,
            location: form.value.location || undefined,
            link: form.value.link || undefined,
        })
        emit('update:modelValue', false)
    }
</script>

<style scoped>
    .calendar-dialog-muted-text {
        color: var(--calendar-muted-text-color, #5f5f5f);
        font-size: 0.75rem;
        line-height: 1rem;
    }
</style>
