<template>
    <v-sheet class="d-flex flex-column overflow-hidden" :class="panelClass" color="transparent" rounded="0"
        :width="panelWidth" :min-width="panelWidth" :max-width="panelWidth">
        <div v-if="showHeader" class="px-4 py-3 border-b flex-shrink-0 d-flex align-center justify-space-between">
            <div>
                <div class="text-subtitle-2 font-weight-bold">{{ title }}</div>
                <div v-if="subtitle" class="calendar-panel-muted-text">{{ subtitle }}</div>
            </div>
            <!-- <v-btn icon size="x-small" variant="text" @click="$emit('create')">
                <v-icon size="14">mdi-plus</v-icon>
                <v-tooltip activator="parent">New event</v-tooltip>
            </v-btn> -->
        </div>
        <v-list density="compact" class="flex-grow-1 min-height-0 overflow-y-auto py-1 px-2">
            <div v-if="events.length === 0" class="d-flex flex-column align-center justify-center py-7">
                <v-icon size="20" class="calendar-empty-icon">mdi-calendar-blank</v-icon>
                <span class="calendar-empty-text mt-1">No matching events</span>
            </div>

            <v-list-item v-for="ev in events" :key="ev.id" :active="selectedEventId === ev.id" rounded="lg"
                class="event-item mb-1 px-2 py-0" slim :ripple="false" @click="$emit('select', ev)"
                @contextmenu.prevent.stop="$emit('contextmenu', { event: ev, mouseEvent: $event })">
                <template #prepend>
                    <v-sheet width="4" rounded="pill" class="mr-2 event-item-strip"
                        :style="{ background: sourceColor(ev.source) }" />
                </template>
                <div class="flex-grow-1 min-width-0">
                    <div class="d-flex align-center ga-2">
                        <div class="event-item-title text-truncate">{{ ev.title }}</div>
                    </div>
                    <div class="event-item-subtitle">{{ eventDateLabel(ev.date) }}</div>
                </div>
                <template v-if="canManageEvent(ev)" #append>
                    <div class="event-item-actions d-flex align-center ga-0">
                        <v-btn icon size="x-small" variant="text" style="width: 22px; height: 22px; min-width: 22px;"
                            @click.stop="$emit('edit', ev)">
                            <v-icon size="14">mdi-pencil</v-icon>
                        </v-btn>
                        <v-btn icon size="x-small" variant="text" color="error"
                            style="width: 22px; height: 22px; min-width: 22px;" @click.stop="$emit('delete', ev)">
                            <v-icon size="14">mdi-delete</v-icon>
                        </v-btn>
                    </div>
                </template>
            </v-list-item>

        </v-list>
    </v-sheet>
</template>

<script setup lang="ts">
    import type { CalEvent } from '@/types/calendar'
    import { normalizeCalendarColor } from '@/utils/calendarColors'

    const props = withDefaults(defineProps<{
        title?: string
        subtitle?: string
        events: CalEvent[]
        selectedEventId?: number | null
        sourceColorMap?: Record<string, string>
        embedded?: boolean
        width?: number
        showHeader?: boolean
    }>(), {
        embedded: false,
        width: 250,
        showHeader: true,
    })

    defineEmits<{
        select: [ev: CalEvent]
        edit: [ev: CalEvent]
        delete: [ev: CalEvent]
        contextmenu: [payload: { event: CalEvent; mouseEvent: MouseEvent }]
    }>()

    const sourceColor = (source: CalEvent['source']) => normalizeCalendarColor(props.sourceColorMap?.[source], '#4ca8df')
    const canManageEvent = (event: CalEvent) => ['user', 'agent'].includes(`${event.source}`)
    const panelClass = computed(() => (
        props.embedded
            ? 'flex-grow-1 min-height-0'
            : 'h-100 border-e'
    ))

    const panelWidth = computed(() => (props.embedded ? undefined : props.width))
    const eventDateLabel = (date: string) => {
        const [_, month, day] = date.split('-')
        if (!month || !day)
            return date

        return `${Number(month)}/${Number(day)}`
    }
</script>

<style scoped>
    .event-item {
        min-height: 34px;
    }

    .event-item-strip {
        align-self: stretch;
        min-height: 24px;
        margin-block: 4px;
    }

    .event-item-title {
        font-size: 0.75rem;
        font-weight: 600;
        line-height: 1rem;
    }

    .event-item-subtitle {
        color: var(--calendar-muted-text-color, #5f5f5f);
        font-size: 0.6875rem;
        line-height: 0.875rem;
    }

    .calendar-panel-muted-text {
        color: var(--calendar-muted-text-color, #5f5f5f);
        font-size: 0.75rem;
        line-height: 1rem;
    }

    .event-item-actions {
        visibility: hidden;
        pointer-events: none;
    }

    .calendar-empty-text {
        color: var(--calendar-muted-text-color, #5f5f5f);
        font-size: 0.6875rem;
        line-height: 0.875rem;
    }

    .calendar-empty-icon {
        color: var(--calendar-muted-text-color, #5f5f5f);
    }

    .event-item:hover .event-item-actions,
    .event-item:focus-within .event-item-actions {
        visibility: visible;
        pointer-events: auto;
    }
</style>
