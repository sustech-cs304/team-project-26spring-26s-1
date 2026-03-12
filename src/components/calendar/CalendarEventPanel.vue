<template>
    <v-sheet class="h-100 d-flex flex-column border-s" color="transparent" rounded="0" width="260">

        <!-- 头部：日期 + 关闭 -->
        <div class="px-4 py-3 border-b flex-shrink-0 d-flex align-center justify-space-between">
            <div>
                <div class="text-subtitle-2 font-weight-bold">{{ formattedDate }}</div>
                <div class="text-caption text-medium-emphasis">{{ events.length }} event{{ events.length !== 1 ? 's' :
                    '' }}</div>
            </div>
            <div class="d-flex ga-1">
                <v-btn icon size="x-small" variant="text" @click="$emit('create')">
                    <v-icon size="14">mdi-plus</v-icon>
                    <v-tooltip activator="parent">New event</v-tooltip>
                </v-btn>
                <v-btn icon size="x-small" variant="text" @click="$emit('close')">
                    <v-icon size="14">mdi-close</v-icon>
                </v-btn>
            </div>
        </div>

        <!-- 事件列表 -->
        <v-list density="compact" class="flex-grow-1 overflow-y-auto py-1">
            <div v-if="events.length === 0" class="d-flex flex-column align-center justify-center py-10">
                <v-icon size="28" style="opacity:0.3;">mdi-calendar-blank</v-icon>
                <span class="text-caption text-disabled mt-2">No events</span>
                <v-btn size="x-small" variant="tonal" class="mt-3" @click="$emit('create')">Add Event</v-btn>
            </div>
            <v-list-item v-for="ev in events" :key="ev.id" :active="selectedEventId === ev.id" active-color="primary"
                rounded="lg" class="mx-1 mb-1 px-3 py-2" @click="$emit('select', ev)">
                <template #prepend>
                    <v-sheet :color="typeColor(ev.type)" width="3" rounded class="flex-shrink-0 mr-3"
                        style="min-height:40px;align-self:stretch;" />
                </template>
                <div class="flex-grow-1 min-width-0">
                    <div class="text-body-2 font-weight-medium text-truncate">{{ ev.title }}</div>
                    <div class="d-flex align-center ga-2 mt-1">
                        <v-chip :color="typeColor(ev.type)" size="x-small" variant="tonal" density="compact">
                            {{ ev.type }}
                        </v-chip>
                        <span v-if="ev.time" class="text-caption text-medium-emphasis">{{ ev.time }}</span>
                    </div>
                    <div v-if="ev.description" class="text-caption text-medium-emphasis mt-1 text-truncate">
                        {{ ev.description }}
                    </div>
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
    import { eventTypeColor } from '@/utils/calendar'

    const props = defineProps<{
        dateKey: string   // 'YYYY-MM-DD'
        events: CalEvent[]
        selectedEventId?: number | null
    }>()

    defineEmits<{
        close: []
        create: []
        select: [ev: CalEvent]
        edit: [ev: CalEvent]
        delete: [ev: CalEvent]
    }>()

    const formattedDate = computed(() => {
        if (!props.dateKey) return ''
        const d = new Date(props.dateKey + 'T00:00:00')
        return d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
    })

    const typeColor = (type: string) => eventTypeColor(type as any)
</script>
