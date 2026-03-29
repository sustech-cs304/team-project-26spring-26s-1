<template>
    <v-sheet class="h-100 d-flex flex-column border-e" color="transparent" rounded="0" width="320">
        <div class="px-4 py-3 border-b flex-shrink-0 d-flex align-center justify-space-between">
            <div>
                <div class="text-subtitle-2 font-weight-bold">{{ title }}</div>
                <div class="text-caption text-medium-emphasis">{{ subtitle }}</div>
            </div>
            <v-btn icon size="x-small" variant="text" @click="$emit('create')">
                <v-icon size="14">mdi-plus</v-icon>
                <v-tooltip activator="parent">New event</v-tooltip>
            </v-btn>
        </div>

        <v-list density="compact" class="flex-grow-1 overflow-y-auto py-1 px-2">
            <div v-if="events.length === 0" class="d-flex flex-column align-center justify-center py-10">
                <v-icon size="28" style="opacity:0.3;">mdi-calendar-blank</v-icon>
                <span class="text-caption text-disabled mt-2">No matching events</span>
            </div>

            <v-list-item v-for="ev in events" :key="ev.id" :active="selectedEventId === ev.id" active-color="primary"
                rounded="lg" class="mb-1 px-2 py-2" @click="$emit('select', ev)">
                <template #prepend>
                    <v-sheet width="4" rounded class="mr-3" :style="{ background: sourceColor(ev.source), minHeight: '40px' }" />
                </template>
                <div class="flex-grow-1 min-width-0">
                    <div class="d-flex align-center justify-space-between ga-2">
                        <div class="text-body-2 font-weight-medium text-truncate">{{ ev.title }}</div>
                        <span class="text-caption text-medium-emphasis flex-shrink-0">#{{ ev.id }}</span>
                    </div>
                    <div class="d-flex align-center ga-2 mt-1 flex-wrap">
                        <v-sheet width="10" height="10" rounded="circle" :style="{ background: eventColor(ev) }" />
                        <v-chip size="x-small" density="compact" variant="outlined" :style="sourceStyle(ev.source)">
                            {{ ev.source }}
                        </v-chip>
                        <span v-if="eventTimeText(ev)" class="text-caption text-medium-emphasis">{{ eventTimeText(ev) }}</span>
                    </div>
                    <div class="text-caption text-medium-emphasis mt-1">{{ ev.date }}</div>
                </div>
                <template #append>
                    <div class="d-flex flex-column ga-1">
                        <v-btn icon size="x-small" variant="text" @click.stop="$emit('edit', ev)">
                            <v-icon size="12">mdi-pencil</v-icon>
                        </v-btn>
                        <v-btn icon size="x-small" variant="text" color="error" @click.stop="$emit('delete', ev)">
                            <v-icon size="12">mdi-delete</v-icon>
                        </v-btn>
                    </div>
                </template>
            </v-list-item>

        </v-list>
    </v-sheet>
</template>

<script setup lang="ts">
    import type { CalEvent } from '@/utils/calendar'
    import { eventSourceRawColor, getEventDisplayTime } from '@/utils/calendar'

    const props = defineProps<{
        title: string
        subtitle: string
        events: CalEvent[]
        selectedEventId?: number | null
    }>()

    defineEmits<{
        create: []
        select: [ev: CalEvent]
        edit: [ev: CalEvent]
        delete: [ev: CalEvent]
    }>()

    const sourceColor = (source: CalEvent['source']) => eventSourceRawColor(source)
    const sourceStyle = (source: CalEvent['source']) => ({ color: sourceColor(source), borderColor: sourceColor(source) })
    const eventColor = (ev: CalEvent) => ev.color || sourceColor(ev.source)

    const eventTimeText = (ev: CalEvent) => getEventDisplayTime(ev)
</script>
