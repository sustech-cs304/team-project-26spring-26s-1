<template>
    <div class="cal-page d-flex flex-column h-100">

        <div class="cal-toolbar px-4 py-2 border-b d-flex align-center justify-space-between flex-shrink-0">
            <div class="d-flex align-center ga-2">
                <v-btn icon size="x-small" variant="text" @click="prevMonth">
                    <v-icon size="16">mdi-chevron-left</v-icon>
                </v-btn>
                <span class="text-subtitle-2 font-weight-bold toolbar-month">{{ monthLabel }}</span>
                <v-btn icon size="x-small" variant="text" @click="nextMonth">
                    <v-icon size="16">mdi-chevron-right</v-icon>
                </v-btn>
                <v-btn size="x-small" variant="outlined" class="ml-1" @click="goToday">Today</v-btn>
            </div>

            <div class="d-flex align-center ga-2">
                <v-btn icon size="x-small" variant="text" @click="searchRailCollapsed = !searchRailCollapsed">
                    <v-icon size="14">{{ searchRailCollapsed ? 'mdi-dock-right' : 'mdi-dock-window' }}</v-icon>
                    <v-tooltip activator="parent">{{ searchRailCollapsed ? 'Show search' : 'Hide search' }}</v-tooltip>
                </v-btn>
                <v-btn size="x-small" color="primary" @click="openCreate(selectedCell?.dateKey ?? todayKey)">
                    <v-icon size="12" class="mr-1">mdi-plus</v-icon>New Event
                </v-btn>
            </div>
        </div>

        <div class="cal-body d-flex flex-grow-1 min-height-0">
            <aside class="left-rail border-e d-flex flex-column">
                <div class="mini-card pa-3 border-b">
                    <div class="d-flex align-center justify-space-between mb-2">
                        <span class="text-caption text-medium-emphasis">Mini Calendar</span>
                        <span class="text-caption font-weight-bold">{{ monthLabel }}</span>
                    </div>
                    <div class="mini-grid">
                        <span v-for="h in miniHeaders" :key="h" class="mini-weekday">{{ h }}</span>
                        <button v-for="c in cells" :key="`mini-${c.dateKey}`" class="mini-day"
                            :class="{ muted: !c.currentMonth, today: c.isToday, active: selectedCell?.dateKey === c.dateKey }"
                            @click="onCellClick(c)">
                            {{ c.day }}
                        </button>
                    </div>
                </div>

                <div class="pa-3 border-b">
                    <div class="text-caption text-medium-emphasis mb-2">Source</div>
                    <div class="filter-strip-list">
                        <v-chip v-for="src in sourceOptions" :key="src.value" class="filter-strip source-strip" size="small" label
                            :variant="activeSource === src.value ? 'flat' : 'outlined'" :style="sourceChipStyle(src.value)"
                            @click="toggleSourceSelection(src.value)">
                            {{ src.label }}
                            <v-btn icon size="x-small" variant="text" class="chip-eye-btn"
                                :aria-label="sourceHighlighted(src.value) ? 'Hide highlight' : 'Show highlight'"
                                @click.stop="toggleSourceHighlight(src.value)">
                                <v-icon size="14">{{ sourceHighlighted(src.value) ? 'mdi-eye' : 'mdi-eye-off' }}</v-icon>
                            </v-btn>
                        </v-chip>
                    </div>
                </div>

            </aside>

            <CalendarEventPanel :title="panelTitle" :subtitle="panelSubtitle" :events="panelEvents"
                :selected-event-id="selectedEventId" @create="openCreate(selectedCell?.dateKey ?? todayKey)"
                @select="onEventClick" @edit="openEdit" @delete="deleteEvent" />

            <section class="cal-grid-wrap flex-grow-1 d-flex flex-column min-width-0" @wheel.prevent="onCalendarWheel">
                <CalendarGrid :cells="cells" :events="displayEvents" :highlighted-sources="highlightedSourceList"
                    :selected-cell="selectedCell" @cell-click="onCellClick" @event-click="onEventClick" />

                <v-card v-if="selectedEventDetail" class="event-floating-card" rounded="lg" elevation="6">
                    <div class="d-flex align-center justify-space-between mb-2">
                        <div class="text-caption text-medium-emphasis">Event Details</div>
                        <v-btn icon size="x-small" variant="text" @click="selectedEventId = null">
                            <v-icon size="14">mdi-close</v-icon>
                        </v-btn>
                    </div>

                    <div class="text-body-2 font-weight-bold mb-2">{{ selectedEventDetail.title }}</div>

                    <div class="floating-row"><span class="label">Event ID</span><span>{{ selectedEventDetail.id }}</span></div>
                    <div class="floating-row"><span class="label">Source</span><span>{{ selectedEventDetail.source }}</span></div>
                    <div class="floating-row"><span class="label">Color</span><span>{{ selectedEventDetail.color || '-' }}</span></div>
                    <div class="floating-row"><span class="label">Start Time</span><span>{{ getEventStartTime(selectedEventDetail) || '-' }}</span></div>
                    <div class="floating-row"><span class="label">End Time</span><span>{{ getEventEndTime(selectedEventDetail) || '-' }}</span></div>
                    <div class="floating-row"><span class="label">Time</span><span>{{ getEventDisplayTime(selectedEventDetail) || '-' }}</span></div>
                    <div class="floating-row"><span class="label">Location</span><span>{{ selectedEventDetail.location || '-' }}</span></div>
                    <div class="floating-row"><span class="label">Description</span><span>{{ selectedEventDetail.description || '-' }}</span></div>
                    <div class="floating-row"><span class="label">Link</span>
                        <a v-if="selectedEventDetail.link" class="floating-link" :href="selectedEventDetail.link" target="_blank" rel="noopener noreferrer">
                            {{ selectedEventDetail.link }}
                        </a>
                        <span v-else>-</span>
                    </div>
                </v-card>
            </section>

            <aside v-if="!searchRailCollapsed" class="search-rail border-s d-flex flex-column">
                <div class="pa-3 border-b">
                    <div class="text-subtitle-2 font-weight-bold">Search Events</div>
                </div>

                <div class="pa-3 d-flex flex-column ga-2">
                    <v-text-field v-model="searchForm.keyword" label="Keyword" density="compact" variant="outlined"
                        hide-details placeholder="title / location / link" />

                    <v-btn size="x-small" variant="text" class="justify-start advanced-toggle"
                        @click="showAdvanced = !showAdvanced">
                        <v-icon size="14" class="mr-1">{{ showAdvanced ? 'mdi-chevron-down' : 'mdi-chevron-right' }}</v-icon>
                        Advanced
                    </v-btn>

                    <v-expand-transition>
                        <div v-show="showAdvanced" class="d-flex flex-column ga-2">
                            <v-text-field v-model="searchForm.id" label="Event ID" density="compact" variant="outlined"
                                hide-details type="number" />
                            <v-select v-model="searchForm.source" :items="dialogSourceItems" label="Source"
                                density="compact" variant="outlined" hide-details clearable />
                            <v-text-field v-model="searchForm.startDate" label="Start Date" density="compact" variant="outlined"
                                type="date" hide-details />
                            <v-text-field v-model="searchForm.endDate" label="End Date" density="compact" variant="outlined"
                                type="date" hide-details />
                        </div>
                    </v-expand-transition>

                    <div class="d-flex ga-2 mt-1">
                        <v-btn size="small" color="primary" :loading="searchLoading" @click="runSearch">Search</v-btn>
                        <v-btn size="small" variant="outlined" @click="resetSearch">Reset</v-btn>
                    </div>

                    <div class="text-caption text-medium-emphasis mt-2">{{ events.length }} result{{ events.length === 1 ? '' : 's' }}</div>
                    <div v-if="searchError" class="text-caption text-error mt-1">{{ searchError }}</div>
                </div>
            </aside>
        </div>

        <CalendarEventDialog v-model="dialogOpen" :event="editingEvent" :default-date="dialogDefaultDate"
            :source-items="dialogSourceItems"
            @submit="saveEvent" />
    </div>
</template>

<script setup lang="ts">
    import CalendarGrid from '@/components/calendar/CalendarGrid.vue'
    import CalendarEventPanel from '@/components/calendar/CalendarEventPanel.vue'
    import CalendarEventDialog from '@/components/calendar/CalendarEventDialog.vue'
    import {
        buildDefaultEvents,
        createCalendarEvent,
        deleteCalendarEvent,
        getCalendarSources,
        searchCalendarEvents,
        updateCalendarEvent,
    } from '@/api/calendar'
    import type { CalEvent, CalendarCell } from '@/utils/calendar'
    import {
        EVENT_SOURCES,
        colorNameToHex,
        eventSourceRawColor,
        getEventDisplayTime,
        getEventEndTime,
        getEventStartTime,
        getEventsForDate,
        nextId,
        toDateKey,
    } from '@/utils/calendar'

    const DAY_MS = 24 * 60 * 60 * 1000

    const startOfWeek = (input: Date) => {
        const d = new Date(input.getFullYear(), input.getMonth(), input.getDate())
        d.setDate(d.getDate() - d.getDay())
        return d
    }

    const addDays = (input: Date, days: number) => {
        const d = new Date(input)
        d.setDate(d.getDate() + days)
        return d
    }

    const shiftVisibleMonth = (offset: number) => {
        const centerDate = addDays(viewStartDate.value, 21)
        const targetMonthStart = new Date(centerDate.getFullYear(), centerDate.getMonth() + offset, 1)
        viewStartDate.value = startOfWeek(targetMonthStart)
    }

    const today = new Date()
    const viewStartDate = ref(startOfWeek(new Date(today.getFullYear(), today.getMonth(), 1)))
    const todayKey = toDateKey(today)

    const events = ref<CalEvent[]>([])
    const selectedCell = ref<CalendarCell | null>(null)
    const selectedEventId = ref<number | null>(null)
    const activeSource = ref<CalEvent['source'] | null>(null)
    const sourceCatalog = ref<{ id: number; title: string; isVisible: boolean; colorHex: string }[]>([])

    const searchForm = reactive({
        keyword: '',
        id: '',
        source: '',
        startDate: '',
        endDate: '',
    })
    const searchLoading = ref(false)
    const searchError = ref('')
    const showAdvanced = ref(false)
    const searchRailCollapsed = ref(false)

    const dialogOpen = ref(false)
    const editingEvent = ref<CalEvent | null>(null)
    const dialogDefaultDate = ref('')
    const lastWheelAt = ref(0)

    const miniHeaders = ['S', 'M', 'T', 'W', 'T', 'F', 'S']
    const sourceOptions = computed<{ value: string; label: string }[]>(() => {
        if (sourceCatalog.value.length === 0) return EVENT_SOURCES
        return sourceCatalog.value.map(item => ({ value: item.title, label: item.title }))
    })
    const dialogSourceItems = computed(() => sourceOptions.value.map(item => ({ title: item.label, value: item.value })))

    const sourceColorMap = computed(() => {
        const map = new Map<string, string>()
        sourceCatalog.value.forEach(item => map.set(item.title, item.colorHex))
        return map
    })

    const highlightedSources = ref(new Set<CalEvent['source']>())

    watch(sourceOptions, (items) => {
        highlightedSources.value = new Set(items.map(item => item.value))
    }, { immediate: true })

    const sourceHighlighted = (source: CalEvent['source']) => highlightedSources.value.has(source)

    const toggleSourceHighlight = (source: CalEvent['source']) => {
        const next = new Set(highlightedSources.value)
        if (next.has(source)) next.delete(source)
        else next.add(source)
        highlightedSources.value = next
    }

    const toggleSourceSelection = (source: CalEvent['source']) => {
        activeSource.value = activeSource.value === source ? null : source
    }

    const highlightedSourceList = computed(() => Array.from(highlightedSources.value))

    const cells = computed<CalendarCell[]>(() => {
        const centerDate = addDays(viewStartDate.value, 21)
        const anchorYear = centerDate.getFullYear()
        const anchorMonth = centerDate.getMonth()
        const todayDateKey = toDateKey(new Date())

        return Array.from({ length: 42 }, (_, index) => {
            const date = addDays(viewStartDate.value, index)
            return {
                day: date.getDate(),
                date,
                dateKey: toDateKey(date),
                currentMonth: date.getFullYear() === anchorYear && date.getMonth() === anchorMonth,
                isToday: toDateKey(date) === todayDateKey,
            }
        })
    })

    const monthLabel = computed(() => {
        const d = addDays(viewStartDate.value, 21)
        return d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    })

    const visibleStart = computed(() => cells.value[0]?.dateKey ?? '')
    const visibleEnd = computed(() => cells.value[cells.value.length - 1]?.dateKey ?? '')

    const toUnixByDateKey = (dateKey: string, tail = '00:00:00') =>
        Math.floor(new Date(`${dateKey}T${tail}`).getTime() / 1000)

    const buildSearchQuery = () => {
        const query: { id?: number; start_time?: number; end_time?: number; source?: string; key_word?: string } = {}

        const id = Number.parseInt(searchForm.id, 10)
        if (Number.isFinite(id)) query.id = id

        const startDate = searchForm.startDate
        const endDate = searchForm.endDate
        if (startDate) query.start_time = toUnixByDateKey(startDate)
        if (endDate) query.end_time = toUnixByDateKey(endDate, '23:59:59')

        const source = `${searchForm.source ?? ''}`.trim()
        if (source) query.source = source

        const keyword = searchForm.keyword.trim()
        if (keyword) query.key_word = keyword

        return query
    }

    const runSearch = async (silent = false): Promise<boolean> => {
        searchLoading.value = true
        if (!silent) searchError.value = ''
        try {
            events.value = await searchCalendarEvents(buildSearchQuery())
            return true
        } catch (error) {
            if (!silent) {
                searchError.value = 'Search failed, showing local fallback data.'
            }
            if (events.value.length === 0) events.value = buildDefaultEvents()
            console.error(error)
            return false
        } finally {
            searchLoading.value = false
        }
    }

    const resetSearch = async () => {
        searchForm.keyword = ''
        searchForm.id = ''
        searchForm.source = ''
        searchForm.startDate = ''
        searchForm.endDate = ''
        showAdvanced.value = false
        await runSearch()
    }

    const loadSources = async () => {
        try {
            const rows = await getCalendarSources()
            sourceCatalog.value = rows.map(row => ({
                id: row.id,
                title: row.title,
                isVisible: row.is_visible,
                colorHex: colorNameToHex(row.color),
            }))
        } catch (error) {
            console.error(error)
            sourceCatalog.value = []
        }
    }

    const visibleRangeEvents = computed(() =>
        events.value.filter(e => {
            const end = e.endDate ?? e.date
            return end >= visibleStart.value && e.date <= visibleEnd.value
        })
    )

    const filteredEvents = computed(() =>
        visibleRangeEvents.value.filter(e => {
            const sourcePass = !activeSource.value || e.source === activeSource.value
            return sourcePass
        })
    )

    const displayEvents = computed(() => visibleRangeEvents.value)

    const selectedDayEvents = computed(() =>
        selectedCell.value ? getEventsForDate(filteredEvents.value, selectedCell.value.dateKey) : []
    )

    const panelEvents = computed(() => {
        const sorted = [...filteredEvents.value].sort((a, b) => {
            const dateCmp = a.date.localeCompare(b.date)
            return dateCmp !== 0 ? dateCmp : getEventStartTime(a).localeCompare(getEventStartTime(b))
        })
        if (!activeSource.value) return selectedDayEvents.value
        return sorted
    })

    const panelTitle = computed(() => {
        if (activeSource.value) {
            return `Source: ${activeSource.value}`
        }
        if (!selectedCell.value) return 'Events'
        return `Date: ${selectedCell.value.dateKey}`
    })

    const panelSubtitle = computed(() => `${panelEvents.value.length} event${panelEvents.value.length === 1 ? '' : 's'}`)
    const selectedEventDetail = computed(() => {
        if (!selectedEventId.value) return null
        return events.value.find(ev => ev.id === selectedEventId.value) ?? null
    })

    const prevMonth = () => {
        shiftVisibleMonth(-1)
    }

    const nextMonth = () => {
        shiftVisibleMonth(1)
    }

    const goToday = () => {
        viewStartDate.value = startOfWeek(new Date())
        const cell = cells.value.find(c => c.dateKey === todayKey)
        if (cell) selectedCell.value = cell
    }

    const onCellClick = (cell: CalendarCell) => {
        selectedCell.value = cell
        selectedEventId.value = null
    }

    const onEventClick = (ev: CalEvent) => {
        selectedEventId.value = ev.id
        const cell = cells.value.find(c => c.dateKey === ev.date)
        if (cell) selectedCell.value = cell
    }

    const onCalendarWheel = (event: WheelEvent) => {
        if (Math.abs(event.deltaY) < 10) return

        const now = Date.now()
        if (now - lastWheelAt.value < 220) return
        lastWheelAt.value = now

        if (event.deltaY > 0) {
            viewStartDate.value = addDays(viewStartDate.value, 7)
            return
        }
        viewStartDate.value = addDays(viewStartDate.value, -7)
    }

    const sourceChipStyle = (source: CalEvent['source']) => {
        const color = sourceColorMap.value.get(source) ?? eventSourceRawColor(source)
        const accent = `color-mix(in srgb, ${color} 48%, #7f8794)`
        const selected = activeSource.value === source
        return sourceHighlighted(source)
            ? {
                '--strip-accent': accent,
                background: `color-mix(in srgb, ${color} 13%, rgb(var(--v-theme-surface)))`,
                color: 'rgba(var(--v-theme-on-surface), 0.9)',
                borderColor: selected ? `color-mix(in srgb, ${color} 45%, rgba(var(--v-theme-on-surface), 0.3))` : 'rgba(var(--v-theme-on-surface), 0.18)',
                boxShadow: selected ? `inset 0 0 0 1px color-mix(in srgb, ${color} 50%, transparent)` : 'none'
            }
            : {
                '--strip-accent': accent,
                background: 'rgba(var(--v-theme-on-surface), 0.02)',
                color: 'rgba(var(--v-theme-on-surface), 0.78)',
                borderColor: selected ? `color-mix(in srgb, ${color} 38%, rgba(var(--v-theme-on-surface), 0.24))` : 'rgba(var(--v-theme-on-surface), 0.12)',
                boxShadow: selected ? `inset 0 0 0 1px color-mix(in srgb, ${color} 42%, transparent)` : 'none'
            }
    }

    const openCreate = (date: string) => {
        editingEvent.value = null
        dialogDefaultDate.value = date
        dialogOpen.value = true
    }

    const openEdit = (ev: CalEvent) => {
        editingEvent.value = ev
        dialogOpen.value = true
    }

    const saveEvent = async (form: Omit<CalEvent, 'id'>) => {
        try {
            if (editingEvent.value) {
                await updateCalendarEvent(editingEvent.value.id, form)
            } else {
                await createCalendarEvent(form)
            }
            await runSearch()
        } catch (error) {
            console.error(error)
            if (editingEvent.value) {
                Object.assign(editingEvent.value, form)
                return
            }
            events.value.push({ id: nextId(events.value), ...form })
        }
    }

    const deleteEvent = async (ev: CalEvent) => {
        try {
            await deleteCalendarEvent(ev.id)
            await runSearch()
        } catch (error) {
            console.error(error)
            events.value = events.value.filter(e => e.id !== ev.id)
            if (selectedEventId.value === ev.id) selectedEventId.value = null
        }
    }

    watch(cells, () => {
        if (selectedCell.value && cells.value.some(c => c.dateKey === selectedCell.value!.dateKey)) return
        selectedCell.value = cells.value.find(c => c.dateKey === todayKey) ?? cells.value[0] ?? null
    }, { immediate: true })

    onMounted(async () => {
        await loadSources()
        const ok = await runSearch(true)
        if (!ok && events.value.length === 0) {
            events.value = buildDefaultEvents()
        }
    })
</script>

<style scoped>
    .cal-page,
    .cal-body,
    .cal-grid-wrap {
        overflow: hidden;
    }

    .cal-grid-wrap {
        position: relative;
    }

    .toolbar-month {
        min-width: 130px;
        text-align: center;
    }

    .left-rail {
        width: 260px;
        min-width: 260px;
        overflow-y: auto;
    }

    .search-rail {
        width: 280px;
        min-width: 280px;
        overflow-y: auto;
        background: color-mix(in srgb, rgb(var(--v-theme-surface)) 92%, #0f172a);
    }

    .advanced-toggle {
        padding-left: 0;
        min-height: 24px;
        color: rgba(var(--v-theme-on-surface), 0.72);
    }

    .filter-strip-list {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    .filter-strip {
        width: 100%;
        min-height: 30px;
        justify-content: flex-start;
        position: relative;
        font-weight: 500;
    }

    .filter-strip :deep(.v-chip__content) {
        width: 100%;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .source-strip {
        border-radius: 8px;
        padding-left: 10px;
    }

    .source-strip::before {
        content: '';
        position: absolute;
        left: 0;
        top: 6px;
        bottom: 6px;
        width: 3px;
        border-radius: 999px;
        background: var(--strip-accent);
    }

    .chip-eye-btn {
        width: 22px;
        height: 22px;
        margin-left: auto;
        margin-right: -4px;
        color: rgba(var(--v-theme-on-surface), 0.62);
    }

    .event-floating-card {
        position: absolute;
        right: 12px;
        top: 44px;
        width: 320px;
        max-height: calc(100% - 56px);
        overflow: auto;
        padding: 10px 12px;
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        background: rgba(var(--v-theme-surface), 0.96);
        backdrop-filter: blur(6px);
        z-index: 3;
    }

    .floating-row {
        display: flex;
        gap: 8px;
        font-size: 12px;
        line-height: 1.4;
        margin-top: 6px;
    }

    .floating-row .label {
        width: 72px;
        flex-shrink: 0;
        color: rgba(var(--v-theme-on-surface), 0.58);
    }

    .floating-link {
        color: rgb(var(--v-theme-primary));
        text-decoration: none;
        word-break: break-all;
    }

    .floating-link:hover {
        text-decoration: underline;
    }

    .mini-grid {
        display: grid;
        grid-template-columns: repeat(7, minmax(0, 1fr));
        gap: 4px;
    }

    .mini-weekday {
        font-size: 10px;
        text-align: center;
        color: rgba(var(--v-theme-on-surface), 0.5);
    }

    .mini-day {
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        border-radius: 6px;
        background: transparent;
        color: rgba(var(--v-theme-on-surface), 0.88);
        font-size: 11px;
        height: 24px;
        cursor: pointer;
    }

    .mini-day.muted {
        opacity: 0.4;
    }

    .mini-day.today {
        border-color: rgb(var(--v-theme-primary));
    }

    .mini-day.active {
        background: rgba(var(--v-theme-primary), 0.15);
        border-color: rgb(var(--v-theme-primary));
    }
</style>
