<template>
    <div class="cal-page d-flex flex-column h-100">

        <!-- 顶栏 -->
        <div class="cal-toolbar px-5 py-2 border-b d-flex align-center justify-space-between flex-shrink-0">
            <div class="d-flex align-center ga-2">
                <v-btn icon size="x-small" variant="text" @click="prevMonth">
                    <v-icon size="16">mdi-chevron-left</v-icon>
                </v-btn>
                <span class="text-subtitle-2 font-weight-bold" style="min-width:130px;text-align:center;">
                    {{ monthLabel }}
                </span>
                <v-btn icon size="x-small" variant="text" @click="nextMonth">
                    <v-icon size="16">mdi-chevron-right</v-icon>
                </v-btn>
                <v-btn size="x-small" variant="outlined" class="ml-1" @click="goToday">Today</v-btn>
            </div>
            <div class="d-flex align-center ga-2">
                <!-- type filter chips -->
                <v-chip v-for="f in typeFilters" :key="f.value" :prepend-icon="f.icon" size="x-small"
                    :variant="activeFilters.includes(f.value) ? 'tonal' : 'text'"
                    :color="activeFilters.includes(f.value) ? 'primary' : undefined" @click="toggleFilter(f.value)">{{
                        f.label }}</v-chip>
                <v-btn size="x-small" color="primary" @click="openCreate(todayKey)">
                    <v-icon size="12" class="mr-1">mdi-plus</v-icon>New Event
                </v-btn>
            </div>
        </div>

        <!-- 主体 -->
        <div class="cal-body d-flex flex-grow-1 min-height-0">

            <!-- 日历网格 -->
            <div class="cal-grid-wrap flex-grow-1 d-flex flex-column min-width-0">
                <CalendarGrid :cells="cells" :events="filteredEvents" :selected-cell="selectedCell"
                    :drag-from="dragFrom" :drag-to="dragTo" @cell-click="onCellClick" @event-click="onEventClick"
                    @drag-start="onDragStart" @drag-enter="onDragEnter" @drag-end="onDragEnd"
                    @context-menu="onContextMenu" />
            </div>

            <!-- 右侧事件面板 -->
            <transition name="panel-slide">
                <CalendarEventPanel v-if="selectedCell" :date-key="selectedCell.dateKey" :events="selectedDayEvents"
                    :selected-event-id="selectedEventId" class="flex-shrink-0" @close="selectedCell = null"
                    @create="openCreate(selectedCell!.dateKey)" @select="ev => selectedEventId = ev.id" @edit="openEdit"
                    @delete="deleteEvent" />
            </transition>

        </div>

        <!-- 右键菜单 -->
        <div v-if="ctxMenu.show" class="ctx-menu" :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
            @click.stop>
            <button class="ctx-item" @click="openCreate(ctxMenu.dateKey); ctxMenu.show = false">
                <v-icon size="13" class="mr-2">mdi-calendar-plus</v-icon>New Event
            </button>
            <button class="ctx-item" @click="pasteEvent(); ctxMenu.show = false" :disabled="!clipboard">
                <v-icon size="13" class="mr-2">mdi-content-paste</v-icon>Paste Event
            </button>
        </div>

        <!-- 拖选批量建事件提示 -->
        <v-snackbar v-model="dragSnackbar" timeout="4000" location="bottom center" color="primary">
            <span class="text-caption">Drag-selected <strong>{{ dragRangeCount }}</strong> day(s).
                <v-btn size="x-small" variant="text" color="white" @click="openBatchCreate">Create Events</v-btn>
            </span>
        </v-snackbar>

        <!-- 事件编辑弹窗 -->
        <CalendarEventDialog v-model="dialogOpen" :event="editingEvent" :default-date="dialogDefaultDate"
            @submit="saveEvent" />

        <!-- 批量建事件弹窗 -->
        <v-dialog v-model="batchDialogOpen" max-width="380">
            <v-card rounded="lg">
                <v-card-title class="text-body-2 font-weight-bold px-4 pt-4 pb-2">
                    Batch Create Events
                </v-card-title>
                <v-card-text class="px-4 py-2 text-caption text-medium-emphasis">
                    Create the same event for {{ dragRangeCount }} selected days ({{ dragFrom?.dateKey }} {{
                        dragTo?.dateKey }}).
                </v-card-text>
                <v-card-text class="px-4 pt-0 pb-3">
                    <v-text-field v-model="batchTitle" label="Event title" density="compact" variant="outlined"
                        hide-details autofocus />
                </v-card-text>
                <v-card-actions class="px-4 py-3 justify-end ga-2">
                    <v-btn variant="outlined" size="small" @click="batchDialogOpen = false">Cancel</v-btn>
                    <v-btn color="primary" size="small" :disabled="!batchTitle.trim()"
                        @click="confirmBatch">Create</v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>

        <!-- 全局点击关闭右键菜单 -->
        <div v-if="ctxMenu.show" class="ctx-overlay" @click="ctxMenu.show = false"
            @contextmenu.prevent="ctxMenu.show = false" />
    </div>
</template>

<script setup lang="ts">
    import CalendarGrid from '@/components/calendar/CalendarGrid.vue'
    import CalendarEventPanel from '@/components/calendar/CalendarEventPanel.vue'
    import CalendarEventDialog from '@/components/calendar/CalendarEventDialog.vue'
    import type { CalEvent, CalendarCell, EventType } from '@/utils/calendar'
    import { buildDefaultEvents } from '@/api/calendar'
    import {
        buildMonthGrid, getEventsForDate,
        nextId, toDateKey, EVENT_TYPE_ICON, EVENT_TYPE_COLOR,
    } from '@/utils/calendar'

    //  State 
    const today = new Date()
    const year = ref(today.getFullYear())
    const month = ref(today.getMonth())
    const todayKey = toDateKey(today)

    const events = ref<CalEvent[]>(buildDefaultEvents())
    const selectedCell = ref<CalendarCell | null>(null)
    const selectedEventId = ref<number | null>(null)
    const clipboard = ref<CalEvent | null>(null)

    // Drag-select
    const dragFrom = ref<CalendarCell | null>(null)
    const dragTo = ref<CalendarCell | null>(null)
    const isDragging = ref(false)
    const dragSnackbar = ref(false)
    const batchDialogOpen = ref(false)
    const batchTitle = ref('')

    // Dialog
    const dialogOpen = ref(false)
    const editingEvent = ref<CalEvent | null>(null)
    const dialogDefaultDate = ref('')

    // Right-click menu
    const ctxMenu = reactive({ show: false, x: 0, y: 0, dateKey: '' })

    // Type filters
    const typeFilters = [
        { value: 'class', label: 'Class', icon: EVENT_TYPE_ICON.class },
        { value: 'exam', label: 'Exam', icon: EVENT_TYPE_ICON.exam },
        { value: 'deadline', label: 'Deadline', icon: EVENT_TYPE_ICON.deadline },
        { value: 'personal', label: 'Personal', icon: EVENT_TYPE_ICON.personal },
        { value: 'meeting', label: 'Meeting', icon: EVENT_TYPE_ICON.meeting },
    ]
    const activeFilters = ref<string[]>([])

    //  Computed 
    const cells = computed(() => buildMonthGrid(year.value, month.value))

    const monthLabel = computed(() => {
        const d = new Date(year.value, month.value, 1)
        return d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    })

    const filteredEvents = computed(() =>
        activeFilters.value.length === 0
            ? events.value
            : events.value.filter(e => activeFilters.value.includes(e.type))
    )

    const selectedDayEvents = computed(() =>
        selectedCell.value ? getEventsForDate(filteredEvents.value, selectedCell.value.dateKey) : []
    )

    const dragRangeKeys = computed(() => {
        if (!dragFrom.value || !dragTo.value) return []
        const a = dragFrom.value.dateKey, b = dragTo.value.dateKey
        const lo = a <= b ? a : b, hi = a <= b ? b : a
        return cells.value.filter(c => c.dateKey >= lo && c.dateKey <= hi).map(c => c.dateKey)
    })

    const dragRangeCount = computed(() => dragRangeKeys.value.length)

    //  Navigation 
    const prevMonth = () => { if (month.value === 0) { month.value = 11; year.value-- } else month.value-- }
    const nextMonth = () => { if (month.value === 11) { month.value = 0; year.value++ } else month.value++ }
    const goToday = () => { year.value = today.getFullYear(); month.value = today.getMonth() }

    //  Filter 
    const toggleFilter = (v: string) => {
        const i = activeFilters.value.indexOf(v)
        i >= 0 ? activeFilters.value.splice(i, 1) : activeFilters.value.push(v)
    }

    //  Grid events 
    const onCellClick = (cell: CalendarCell) => {
        if (isDragging.value) return
        selectedCell.value = (selectedCell.value?.dateKey === cell.dateKey) ? null : cell
        selectedEventId.value = null
    }

    const onEventClick = (ev: CalEvent) => {
        selectedEventId.value = ev.id
        const cell = cells.value.find(c => c.dateKey === ev.date) ?? null
        if (cell) selectedCell.value = cell
    }

    //  Drag-select 
    const onDragStart = (cell: CalendarCell) => { dragFrom.value = cell; dragTo.value = cell; isDragging.value = true }
    const onDragEnter = (cell: CalendarCell) => { if (isDragging.value) dragTo.value = cell }
    const onDragEnd = (cell: CalendarCell) => {
        isDragging.value = false
        dragTo.value = cell
        if (dragRangeCount.value > 1) dragSnackbar.value = true
        else { dragFrom.value = null; dragTo.value = null }
    }

    const openBatchCreate = () => { batchTitle.value = ''; batchDialogOpen.value = true; dragSnackbar.value = false }

    const confirmBatch = () => {
        const title = batchTitle.value.trim()
        if (!title) return
        dragRangeKeys.value.forEach(dateKey => {
            events.value.push({ id: nextId(events.value), title, type: 'personal', date: dateKey, time: '' })
        })
        batchDialogOpen.value = false
        dragFrom.value = null; dragTo.value = null
    }

    //  Context menu 
    const onContextMenu = ({ cell, event }: { cell: CalendarCell; event: MouseEvent }) => {
        ctxMenu.show = true
        ctxMenu.x = event.clientX
        ctxMenu.y = event.clientY
        ctxMenu.dateKey = cell.dateKey
    }

    const pasteEvent = () => {
        if (!clipboard.value) return
        events.value.push({ ...clipboard.value, id: nextId(events.value), date: ctxMenu.dateKey })
    }

    //  CRUD 
    const openCreate = (date: string) => {
        editingEvent.value = null; dialogDefaultDate.value = date; dialogOpen.value = true
    }
    const openEdit = (ev: CalEvent) => { editingEvent.value = ev; dialogOpen.value = true }

    const saveEvent = (form: any) => {
        if (editingEvent.value) {
            Object.assign(editingEvent.value, form)
        } else {
            events.value.push({ id: nextId(events.value), ...form })
        }
    }

    const deleteEvent = (ev: CalEvent) => {
        clipboard.value = ev
        events.value = events.value.filter(e => e.id !== ev.id)
        if (selectedEventId.value === ev.id) selectedEventId.value = null
    }
</script>

<style scoped>
    .cal-page {
        overflow: hidden;
    }

    .cal-body {
        overflow: hidden;
    }

    .cal-grid-wrap {
        overflow: hidden;
    }

    /* right-click menu */
    .ctx-overlay {
        position: fixed;
        inset: 0;
        z-index: 999;
    }

    .ctx-menu {
        position: fixed;
        z-index: 1000;
        min-width: 160px;
        background: rgb(var(--v-theme-surface));
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        border-radius: 8px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.14);
        padding: 4px;
        overflow: hidden;
    }

    .ctx-item {
        display: flex;
        align-items: center;
        width: 100%;
        padding: 6px 10px;
        font-size: 12px;
        font-weight: 500;
        border: none;
        border-radius: 5px;
        cursor: pointer;
        color: rgba(var(--v-theme-on-surface), 0.85);
        background: transparent;
        transition: background 0.12s;
    }

    .ctx-item:hover {
        background: rgba(var(--v-theme-surface-variant), 0.5);
    }

    .ctx-item:disabled {
        opacity: 0.4;
        cursor: default;
    }

    /* panel slide animation */
    .panel-slide-enter-active,
    .panel-slide-leave-active {
        transition: all 0.2s ease;
    }

    .panel-slide-enter-from,
    .panel-slide-leave-to {
        transform: translateX(20px);
        opacity: 0;
    }
</style>
