<template>
    <div class="cal-grid">
        <!-- 星期头 -->
        <div v-for="d in dayHeaders" :key="d" class="cal-weekday">{{ d }}</div>

        <!-- 日期格子 -->
        <div v-for="(cell, idx) in cells" :key="idx" class="cal-cell" :class="{
            'other-month': !cell.currentMonth,
            'is-today': cell.isToday,
            'is-selected': isSelected(cell),
            'drag-range': inDragRange(cell),
        }" @click="$emit('cellClick', cell)" @mousedown="$emit('dragStart', cell)"
            @mouseenter="$emit('dragEnter', cell)" @mouseup="$emit('dragEnd', cell)"
            @contextmenu.prevent="$emit('contextMenu', { cell, event: $event })">
            <!-- 日期数字 -->
            <div class="d-flex align-center">
                <span class="cell-date-num" :class="{ today: cell.isToday }">{{ cell.day }}</span>
            </div>
            <!-- 事件 chips -->
            <div class="cell-events">
                <CalendarEventChip v-for="ev in visibleEvents(cell)" :key="ev.id" :event="ev"
                    @click="$emit('eventClick', ev)" />
                <span v-if="hiddenCount(cell) > 0" class="text-caption text-disabled"
                    style="font-size:10px;padding-left:5px;">+{{ hiddenCount(cell) }} more</span>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
    import type { CalendarCell, CalEvent } from '@/utils/calendar'
    import { getEventsForDate } from '@/utils/calendar'
    import CalendarEventChip from './CalendarEventChip.vue'

    const props = defineProps<{
        cells: CalendarCell[]
        events: CalEvent[]
        selectedCell?: CalendarCell | null
        dragFrom?: CalendarCell | null
        dragTo?: CalendarCell | null
    }>()

    defineEmits<{
        cellClick: [cell: CalendarCell]
        eventClick: [event: CalEvent]
        dragStart: [cell: CalendarCell]
        dragEnter: [cell: CalendarCell]
        dragEnd: [cell: CalendarCell]
        contextMenu: [payload: { cell: CalendarCell; event: MouseEvent }]
    }>()

    const dayHeaders = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    const MAX_CHIPS = 3

    const cellEvents = (cell: CalendarCell) => getEventsForDate(props.events, cell.dateKey)
    const visibleEvents = (cell: CalendarCell) => cellEvents(cell).slice(0, MAX_CHIPS)
    const hiddenCount = (cell: CalendarCell) => Math.max(0, cellEvents(cell).length - MAX_CHIPS)

    const isSelected = (cell: CalendarCell) => props.selectedCell?.dateKey === cell.dateKey

    const inDragRange = (cell: CalendarCell) => {
        if (!props.dragFrom || !props.dragTo) return false
        const a = props.dragFrom.dateKey, b = props.dragTo.dateKey
        const lo = a <= b ? a : b, hi = a <= b ? b : a
        return cell.dateKey >= lo && cell.dateKey <= hi
    }
</script>

<style scoped>

    /* 日历 CSS Grid 布局（Vuetify 无法实现 7 列日历格式） */
    .cal-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        border-left: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        flex: 1;
        min-height: 0;
    }

    .cal-weekday {
        padding: 4px 0;
        font-size: 11px;
        font-weight: 600;
        text-align: center;
        color: rgba(var(--v-theme-on-surface), 0.45);
        letter-spacing: .04em;
        text-transform: uppercase;
        border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    }

    .cal-cell {
        border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        padding: 4px 5px 3px;
        min-height: 80px;
        cursor: pointer;
        display: flex;
        flex-direction: column;
        gap: 2px;
        user-select: none;
        transition: background 0.1s;
    }

    .cal-cell:hover {
        background: rgba(var(--v-theme-surface-variant), 0.3);
    }

    .cal-cell.is-selected {
        background: rgba(var(--v-theme-primary), 0.08);
    }

    .cal-cell.drag-range {
        background: rgba(var(--v-theme-primary), 0.12);
    }

    .cal-cell.other-month {
        opacity: 0.38;
    }

    /* 今天高亮圆圈（Vuetify 无原生日历格实现） */
    .cell-date-num {
        font-size: 11px;
        font-weight: 500;
        width: 20px;
        height: 20px;
        line-height: 20px;
        text-align: center;
        border-radius: 50%;
    }

    .cell-date-num.today {
        background: rgb(var(--v-theme-primary));
        color: rgb(var(--v-theme-on-primary));
        font-weight: 700;
    }

    .cell-events {
        display: flex;
        flex-direction: column;
        gap: 1px;
        overflow: hidden;
    }
</style>
