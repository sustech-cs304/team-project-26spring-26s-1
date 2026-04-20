<template>
    <v-sheet class="d-flex flex-column overflow-hidden" :class="panelClass" color="transparent" rounded="0"
        :width="panelWidth" :min-width="panelWidth" :max-width="panelWidth">
        <div class="px-4 py-3 border-b flex-shrink-0 d-flex align-center justify-space-between">
            <div>
                <div class="text-subtitle-2 font-weight-bold">{{ title }}</div>
                <div v-if="subtitle" class="text-caption text-medium-emphasis">{{ subtitle }}</div>
            </div>
            <!-- <v-btn icon size="x-small" variant="text" @click="$emit('create')">
                <v-icon size="14">mdi-plus</v-icon>
                <v-tooltip activator="parent">New event</v-tooltip>
            </v-btn> -->
        </div>
        <v-list density="compact" class="flex-grow-1 min-height-0 overflow-y-auto py-1 px-2">
            <div v-if="events.length === 0" class="d-flex flex-column align-center justify-center py-10">
                <v-icon size="28" style="opacity:0.3;">mdi-calendar-blank</v-icon>
                <span class="text-caption text-disabled mt-2">No matching events</span>
            </div>

            <v-list-item v-for="ev in events" :key="ev.id" :active="selectedEventId === ev.id" active-color="primary"
                rounded="lg" class="event-item mb-1 px-1 py-0" @click="$emit('select', ev)"
                @contextmenu.prevent.stop="$emit('contextmenu', { event: ev, mouseEvent: $event })">
                <template #prepend>
                    <v-sheet width="4" rounded class="mr-3"
                        :style="{ background: sourceColor(ev.source), minHeight: '32px' }" />
                </template>
                <div class="flex-grow-1 min-width-0">
                    <div class="d-flex align-center ga-2">
                        <div class="text-caption font-weight-medium text-truncate">{{ ev.title }}</div>
                    </div>
                    <div class="text-caption text-medium-emphasis mt-0">{{ eventDateLabel(ev.date) }}</div>
                </div>
                <template #append>
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

    const props = withDefaults(defineProps<{
        title: string
        subtitle: string
        events: CalEvent[]
        selectedEventId?: number | null
        sourceColorMap?: Record<string, string>
        embedded?: boolean
        width?: number
    }>(), {
        embedded: false,
        width: 250,
    })

    defineEmits<{
        select: [ev: CalEvent]
        edit: [ev: CalEvent]
        delete: [ev: CalEvent]
        contextmenu: [payload: { event: CalEvent; mouseEvent: MouseEvent }]
    }>()

    const sourceColor = (source: CalEvent['source']) => props.sourceColorMap?.[source] ?? '#2563eb'
    const panelClass = computed(() => (
        props.embedded
            ? 'flex-grow-1 min-height-0 border-t'
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
    .event-item-actions {
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.16s ease;
    }

    .event-item:hover .event-item-actions,
    .event-item:focus-within .event-item-actions {
        opacity: 1;
        pointer-events: auto;
    }
</style>
