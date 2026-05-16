<template>
    <div ref="gridEl" class="cal-grid h-100 min-height-0" :style="gridStyle"
        @dragstart="onGridNativeDragStart" @dragover="onGridDragOver" @dragleave="onGridDragLeave" @drop="onGridDrop">
        <!-- 星期头 -->
        <div v-for="(d, index) in dayHeaders" :key="d" class="calendar-grid-header py-1 text-center font-weight-bold text-uppercase border-b" :class="{ 'border-e': !isLastColumn(index) }">
            {{ d }}
        </div>

        <!-- 日期格子 -->
        <v-sheet v-for="(cell, idx) in cells" :key="idx" color="transparent" rounded="0" draggable="false"
            class="d-flex flex-column ga-1 px-1 pt-1 pb-1 border-b overflow-hidden min-height-0 calendar-cell"
            :class="{
                'border-e': !isLastColumn(idx),
                'calendar-cell--selected': isSelected(cell),
                'calendar-cell--muted': !cell.currentMonth,
                'calendar-cell--drop-target': dropTargetDateKey === cell.dateKey,
            }"
            :style="cellStyle(cell)" @click="$emit('cellClick', cell)">
            <!-- 日期数字 -->
            <v-avatar size="20" draggable="false" class="calendar-date-avatar align-self-end" :color="cell.isToday ? 'primary' : undefined" :variant="cell.isToday ? 'flat' : 'text'" :class="cell.isToday ? 'font-weight-bold' : 'font-weight-medium'" style="font-size:11px;">
                {{ cell.day }}
            </v-avatar>
            <!-- 事件 chips -->
            <div class="calendar-cell-events d-flex flex-column flex-grow-1 overflow-hidden">
                <CalendarEventChip v-for="ev in visibleEvents(cell)" :key="ev.id" :event="ev"
                    :source-color-map="sourceColorMap"
                    :draggable="isDraggable(ev)"
                    :selected="selectedEventId === ev.id"
                    @click="$emit('eventClick', ev)"
                    @contextmenu="$emit('eventContextMenu', $event)"
                    @dragstart="onEventDragStart"
                    @dragend="onEventDragEnd" />
                <span v-if="hiddenCount(cell) > 0" class="calendar-hidden-count text-truncate ps-1">
                    +{{ hiddenCount(cell) }} more
                </span>
            </div>
        </v-sheet>
    </div>
</template>

<script setup lang="ts">
    import type { CSSProperties } from 'vue'
    import { useTheme } from 'vuetify'
    import type { CalendarCell, CalEvent } from '@/types/calendar'
    import { getEventsForDate } from '@/utils/calendar'
    import CalendarEventChip from './CalendarEventChip.vue'

    const props = defineProps<{
        cells: CalendarCell[]
        events: CalEvent[]
        sourceColorMap?: Record<string, string>
        selectedCell?: CalendarCell | null
        selectedEventId?: number | null
    }>()

    const emit = defineEmits<{
        cellClick: [cell: CalendarCell]
        eventClick: [event: CalEvent]
        eventContextMenu: [payload: { event: CalEvent; mouseEvent: MouseEvent }]
        eventDrop: [payload: { event: CalEvent; dateKey: string }]
    }>()

    const dayHeaders = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    const MAX_CHIPS = 3
    const GRID_HEADER_HEIGHT = 28
    const GRID_COLUMNS = 7
    const GRID_ROWS = 6
    const theme = useTheme()
    const gridEl = ref<HTMLElement | null>(null)
    const draggedEvent = ref<CalEvent | null>(null)
    const dropTargetDateKey = ref<string | null>(null)
    let latestDragPoint: { x: number; y: number } | null = null
    let dragFrameId: number | null = null

    const cellEvents = (cell: CalendarCell) => getEventsForDate(props.events, cell.dateKey)
    const visibleEvents = (cell: CalendarCell) => cellEvents(cell).slice(0, MAX_CHIPS)
    const hiddenCount = (cell: CalendarCell) => Math.max(0, cellEvents(cell).length - MAX_CHIPS)

    const isDraggable = (event: CalEvent) => event.source === 'user' && event.id >= 0

    const onEventDragStart = (payload: { event: CalEvent; dragEvent: DragEvent }) => {
        draggedEvent.value = payload.event
        payload.dragEvent.dataTransfer?.setData('application/x-opencrab-calendar-event-id', `${payload.event.id}`)
    }

    const onGridNativeDragStart = (event: DragEvent) => {
        if ((event.target as HTMLElement | null)?.closest('.calendar-event-chip')) return
        event.preventDefault()
    }

    const cancelDragFrame = () => {
        if (dragFrameId === null) return
        window.cancelAnimationFrame(dragFrameId)
        dragFrameId = null
    }

    const resetDragState = () => {
        cancelDragFrame()
        draggedEvent.value = null
        dropTargetDateKey.value = null
        latestDragPoint = null
    }

    const onEventDragEnd = () => {
        resetDragState()
    }

    const resolveDateKeyFromPoint = (x: number, y: number) => {
        const rect = gridEl.value?.getBoundingClientRect()
        if (!rect) return null
        if (x < rect.left || x > rect.right || y < rect.top + GRID_HEADER_HEIGHT || y > rect.bottom) return null

        const column = Math.min(GRID_COLUMNS - 1, Math.max(0, Math.floor((x - rect.left) / (rect.width / GRID_COLUMNS))))
        const row = Math.min(GRID_ROWS - 1, Math.max(0, Math.floor((y - rect.top - GRID_HEADER_HEIGHT) / ((rect.height - GRID_HEADER_HEIGHT) / GRID_ROWS))))
        return props.cells[(row * GRID_COLUMNS) + column]?.dateKey ?? null
    }

    const updateDropTargetFromPoint = () => {
        dragFrameId = null
        const point = latestDragPoint
        if (!point) return
        dropTargetDateKey.value = resolveDateKeyFromPoint(point.x, point.y)
    }

    const scheduleDropTargetUpdate = () => {
        if (dragFrameId !== null) return
        dragFrameId = window.requestAnimationFrame(updateDropTargetFromPoint)
    }

    const onGridDragOver = (event: DragEvent) => {
        if (!draggedEvent.value) return
        event.preventDefault()
        if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
        latestDragPoint = { x: event.clientX, y: event.clientY }
        scheduleDropTargetUpdate()
    }

    const onGridDragLeave = (event: DragEvent) => {
        if (!draggedEvent.value) return
        const rect = gridEl.value?.getBoundingClientRect()
        if (!rect) return
        const outside = event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom
        if (outside) dropTargetDateKey.value = null
    }

    const onGridDrop = (event: DragEvent) => {
        const currentEvent = draggedEvent.value
        if (!currentEvent) return
        event.preventDefault()
        event.stopPropagation()
        const dateKey = resolveDateKeyFromPoint(event.clientX, event.clientY) ?? dropTargetDateKey.value
        resetDragState()
        if (!dateKey) return
        emit('eventDrop', { event: currentEvent, dateKey })
    }

    const isSelected = (cell: CalendarCell) => props.selectedCell?.dateKey === cell.dateKey
    const isLastColumn = (index: number) => index % 7 === 6

    const cellStyle = (cell: CalendarCell): CSSProperties => ({
        cursor: 'pointer',
        userSelect: 'none',
    })
    const gridStyle = computed<CSSProperties>(() => ({
        '--calendar-selected-cell-bg': theme.current.value.dark ? '#202a33' : '#eaf3ff',
        '--calendar-drop-cell-bg': theme.current.value.dark ? '#18232c' : '#f2f8ff',
        '--calendar-muted-cell-color': theme.current.value.dark ? '#747474' : '#9a9a9a',
        '--calendar-grid-header-color': theme.current.value.dark ? '#b8b8b8' : '#5f5f5f',
        '--calendar-subtle-text-color': theme.current.value.dark ? '#8a8a8a' : '#8a8a8a',
    }))

    onBeforeUnmount(cancelDragFrame)
</script>

<style scoped>
    .cal-grid {
        --calendar-selected-cell-bg: #eaf3ff;
        --calendar-drop-cell-bg: #f2f8ff;
        --calendar-muted-cell-color: #9a9a9a;
        --calendar-grid-header-color: #5f5f5f;
        --calendar-subtle-text-color: #8a8a8a;

        display: grid;
        grid-template-columns: repeat(7, 1fr);
        grid-template-rows: 28px repeat(6, minmax(0, 1fr));
    }

    .calendar-cell {
        transition: background-color 0.12s ease, box-shadow 0.12s ease;
    }

    .calendar-cell-events {
        gap: 1px;
        min-height: 0;
        padding-right: 8px;
    }

    .calendar-date-avatar {
        user-select: none;
        -webkit-user-drag: none;
    }

    .calendar-grid-header {
        color: var(--calendar-grid-header-color);
        font-size: 11px;
        letter-spacing: 0.04em;
    }

    .calendar-hidden-count {
        color: var(--calendar-subtle-text-color);
        font-size: 10px;
        line-height: 14px;
    }

    .calendar-cell--muted {
        color: var(--calendar-muted-cell-color);
    }

    .calendar-cell--selected {
        background: var(--calendar-selected-cell-bg) !important;
    }

    .calendar-cell--drop-target {
        box-shadow: inset 0 0 0 1px rgb(var(--v-theme-primary));
        background: var(--calendar-drop-cell-bg) !important;
    }

</style>
