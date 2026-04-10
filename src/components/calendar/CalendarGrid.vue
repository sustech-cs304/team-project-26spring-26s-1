<template>
    <div class="cal-grid border-s border-t h-100 min-height-0">
        <!-- 星期头 -->
        <div v-for="d in dayHeaders" :key="d" class="py-1 text-center text-caption font-weight-bold text-uppercase text-medium-emphasis border-e border-b" style="font-size:11px;letter-spacing:.04em;">
            {{ d }}
        </div>

        <!-- 日期格子 -->
        <v-sheet v-for="(cell, idx) in cells" :key="idx" color="transparent" rounded="0" class="d-flex flex-column ga-1 px-1 pt-1 pb-1 border-e border-b overflow-hidden min-height-0" :style="cellStyle(cell)" @click="$emit('cellClick', cell)">
            <!-- 日期数字 -->
            <v-avatar size="20" :color="cell.isToday ? 'primary' : undefined" :variant="cell.isToday ? 'flat' : 'text'" :class="cell.isToday ? 'font-weight-bold' : 'font-weight-medium'" style="font-size:11px;">
                {{ cell.day }}
            </v-avatar>
            <!-- 事件 chips -->
            <div class="d-flex flex-column flex-grow-1 overflow-hidden" style="gap:1px;min-height:0;">
                <CalendarEventChip v-for="ev in visibleEvents(cell)" :key="ev.id" :event="ev"
                    :source-color-map="sourceColorMap"
                    :dimmed="isDimmed(ev)"
                    @click="$emit('eventClick', ev)"
                    @contextmenu="$emit('eventContextMenu', $event)" />
                <span v-if="hiddenCount(cell) > 0" class="text-caption text-disabled text-truncate ps-1" 
                    style="font-size:10px;">
                    +{{ hiddenCount(cell) }} more
                </span>
            </div>
        </v-sheet>
    </div>
</template>

<script setup lang="ts">
    import type { CSSProperties } from 'vue'
    import type { CalendarCell, CalEvent } from '@/types/calendar'
    import { getEventsForDate } from '@/utils/calendar'
    import CalendarEventChip from './CalendarEventChip.vue'

    const props = defineProps<{
        cells: CalendarCell[]
        events: CalEvent[]
        highlightedSources?: CalEvent['source'][]
        sourceColorMap?: Record<string, string>
        selectedCell?: CalendarCell | null
    }>()

    defineEmits<{
        cellClick: [cell: CalendarCell]
        eventClick: [event: CalEvent]
        eventContextMenu: [payload: { event: CalEvent; mouseEvent: MouseEvent }]
    }>()

    const dayHeaders = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    const MAX_CHIPS = 3

    const cellEvents = (cell: CalendarCell) => getEventsForDate(props.events, cell.dateKey)
    const visibleEvents = (cell: CalendarCell) => cellEvents(cell).slice(0, MAX_CHIPS)
    const hiddenCount = (cell: CalendarCell) => Math.max(0, cellEvents(cell).length - MAX_CHIPS)

    const isDimmed = (event: CalEvent) => {
        const sourceOn = props.highlightedSources?.includes(event.source) ?? true
        return !sourceOn
    }

    const isSelected = (cell: CalendarCell) => props.selectedCell?.dateKey === cell.dateKey

    const cellStyle = (cell: CalendarCell): CSSProperties => ({
        cursor: 'pointer',
        userSelect: 'none',
        opacity: cell.currentMonth ? 1 : 0.6,
        background: isSelected(cell) ? 'rgba(var(--v-theme-primary), 0.08)' : undefined,
    })
</script>

<style scoped>
    .cal-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        grid-template-rows: 28px repeat(6, minmax(0, 1fr));
    }
</style>
