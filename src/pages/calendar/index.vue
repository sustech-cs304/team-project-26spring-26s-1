<template>
    <v-sheet color="surface" class="d-flex flex-column h-100 overflow-hidden">
        <v-sheet class="d-flex flex-grow-1 min-height-0 overflow-hidden">
            <v-sheet width="250" min-width="250" max-width="250"
                class="border-e d-flex flex-column min-height-0 overflow-hidden">
                <v-sheet class="d-flex flex-column flex-shrink-0 overflow-y-auto">
                    <v-sheet class="pa-3 border-b">
                        <v-sheet class="d-flex align-center justify-space-between ga-1 mb-2">
                            <v-btn icon size="x-small" variant="text" @click="prevMonth">
                                <v-icon size="16">mdi-chevron-left</v-icon>
                            </v-btn>
                            <span class="text-caption font-weight-bold text-center flex-grow-1">{{ monthLabel }}</span>
                            <v-btn icon size="x-small" variant="text" @click="nextMonth">
                                <v-icon size="16">mdi-chevron-right</v-icon>
                            </v-btn>
                        </v-sheet>
                        <v-sheet style="display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 4px;">
                            <span v-for="h in miniHeaders" :key="h" style="font-size: 10px; text-align: center; color: rgba(var(--v-theme-on-surface), 0.5);">{{ h }}</span>
                            <button v-for="c in cells" :key="`mini-${c.dateKey}`" class="mini-day-btn"
                                :class="{ muted: !c.currentMonth, today: c.isToday, active: selectedCell?.dateKey === c.dateKey }"
                                @click="onCellClick(c)">
                                {{ c.day }}
                            </button>
                        </v-sheet>
                    </v-sheet>

                    <v-sheet class="pa-3 border-b">
                        <v-sheet class="text-caption text-medium-emphasis mb-2">Source</v-sheet>
                        <v-sheet class="d-flex flex-column ga-2">
                            <v-chip v-for="src in sourceOptions" :key="src.value" class="source-chip" size="small" label
                                :variant="activeSource === src.value ? 'flat' : 'outlined'" :style="sourceChipStyle(src.value)"
                                @click="toggleSourceSelection(src.value)">
                                <v-sheet class="d-flex align-center w-100 ga-2">
                                    <v-sheet class="flex-shrink-0" width="4" rounded="pill"
                                        style="align-self: stretch; margin: 2px 0; background: var(--strip-accent);" />
                                    <span>{{ src.label }}</span>
                                    <v-btn icon size="x-small" variant="text"
                                        style="width: 22px; height: 22px; margin-left: auto; margin-right: -4px; color: rgba(var(--v-theme-on-surface), 0.62);"
                                        :aria-label="sourceHighlighted(src.value) ? 'Hide highlight' : 'Show highlight'"
                                        @click.stop="toggleSourceHighlight(src.value)">
                                        <v-icon size="14">{{ sourceHighlighted(src.value) ? 'mdi-eye' : 'mdi-eye-off' }}</v-icon>
                                    </v-btn>
                                    <v-btn icon size="x-small" variant="text"
                                        style="width: 22px; height: 22px; margin-right: -4px; color: rgba(var(--v-theme-on-surface), 0.62);"
                                        aria-label="Edit source color" @click.stop="openSourceColorDialog(src.value)">
                                        <v-icon size="14">mdi-palette</v-icon>
                                    </v-btn>
                                </v-sheet>
                            </v-chip>
                        </v-sheet>
                    </v-sheet>
                </v-sheet>

                <CalendarEventPanel embedded :title="panelTitle" :subtitle="panelSubtitle" :events="panelEvents"
                    :selected-event-id="selectedEventId" :source-color-map="resolvedSourceColorMap"
                    @select="onEventClick" @edit="openEdit" @delete="deleteEvent"
                    @contextmenu="openEventContextMenu" />
            </v-sheet>

            <v-sheet class="flex-grow-1 d-flex flex-column min-width-0 min-height-0 overflow-hidden">
                <v-sheet class="px-4 py-2 border-s border-e border-b d-flex align-center justify-end flex-shrink-0">
                    <v-sheet class="d-flex align-center ga-2">
                        <v-btn size="small" variant="outlined" @click="goToday">Today</v-btn>
                        <v-btn icon size="small" variant="text" @click="searchRailCollapsed = !searchRailCollapsed">
                            <v-icon size="14">{{ searchRailCollapsed ? 'mdi-dock-right' : 'mdi-dock-window' }}</v-icon>
                            <v-tooltip activator="parent" location="bottom">{{ searchRailCollapsed ? 'Show search' : 'Hide search' }}</v-tooltip>
                        </v-btn>
                        <v-btn size="small" color="primary" @click="openCreate(selectedCell?.dateKey ?? todayKey)">
                            <v-icon size="12" class="mr-1">mdi-plus</v-icon>New Event
                        </v-btn>
                    </v-sheet>
                </v-sheet>

                <section class="flex-grow-1 d-flex flex-column min-width-0 min-height-0 border-s border-e border-b"
                    style="overflow: hidden; position: relative;" @wheel.prevent="onCalendarWheel">
                    <CalendarGrid :cells="cells" :events="displayEvents" :highlighted-sources="highlightedSourceList"
                        :selected-cell="selectedCell" :source-color-map="resolvedSourceColorMap"
                        @cell-click="onCellClick" @event-click="onEventClick" @event-context-menu="openEventContextMenu" />

                    <v-card v-if="selectedEventDetail" class="event-details-card" rounded="lg" elevation="6">
                        <v-sheet class="d-flex align-center justify-space-between mb-2">
                            <v-sheet class="text-caption text-medium-emphasis">Event Details</v-sheet>
                            <v-btn icon size="x-small" variant="text" @click="selectedEventId = null">
                                <v-icon size="14">mdi-close</v-icon>
                            </v-btn>
                        </v-sheet>

                        <v-sheet class="text-body-2 font-weight-bold mb-2">{{ selectedEventDetail.title }}</v-sheet>

                        <v-sheet class="event-detail-row"><span style="width: 72px; flex-shrink: 0; color: rgba(var(--v-theme-on-surface), 0.58);">Source</span><span>{{ selectedEventDetail.source }}</span></v-sheet>
                        <v-sheet class="event-detail-row"><span style="width: 72px; flex-shrink: 0; color: rgba(var(--v-theme-on-surface), 0.58);">Color</span><span>{{ selectedEventDetail.color || '-' }}</span></v-sheet>
                        <v-sheet class="event-detail-row"><span style="width: 72px; flex-shrink: 0; color: rgba(var(--v-theme-on-surface), 0.58);">Start Time</span><span>{{ getEventStartTime(selectedEventDetail) || '-' }}</span></v-sheet>
                        <v-sheet class="event-detail-row"><span style="width: 72px; flex-shrink: 0; color: rgba(var(--v-theme-on-surface), 0.58);">End Time</span><span>{{ getEventEndTime(selectedEventDetail) || '-' }}</span></v-sheet>
                        <v-sheet class="event-detail-row"><span style="width: 72px; flex-shrink: 0; color: rgba(var(--v-theme-on-surface), 0.58);">Time</span><span>{{ getEventDisplayTime(selectedEventDetail) || '-' }}</span></v-sheet>
                        <v-sheet class="event-detail-row"><span style="width: 72px; flex-shrink: 0; color: rgba(var(--v-theme-on-surface), 0.58);">Location</span><span>{{ selectedEventDetail.location || '-' }}</span></v-sheet>
                        <v-sheet class="event-detail-row"><span style="width: 72px; flex-shrink: 0; color: rgba(var(--v-theme-on-surface), 0.58);">Description</span><span>{{ selectedEventDetail.description || '-' }}</span></v-sheet>
                        <v-sheet class="event-detail-row"><span style="width: 72px; flex-shrink: 0; color: rgba(var(--v-theme-on-surface), 0.58);">Link</span>
                            <a v-if="selectedEventDetail.link" class="event-detail-link"
                                :href="selectedEventDetail.link" target="_blank" rel="noopener noreferrer">
                                {{ selectedEventDetail.link }}
                            </a>
                            <span v-else>-</span>
                        </v-sheet>
                    </v-card>
                </section>
            </v-sheet>


            <aside v-if="!searchRailCollapsed" class="border-s d-flex flex-column"
                style="width: 280px; min-width: 280px; overflow-y: auto; background: color-mix(in srgb, rgb(var(--v-theme-surface)) 92%, #0f172a);">
                <v-sheet class="pa-3 border-b">
                    <v-sheet class="text-subtitle-2 font-weight-bold">Search Events</v-sheet>
                </v-sheet>

                <v-sheet class="pa-3 d-flex flex-column ga-2">
                    <v-text-field v-model="searchForm.keyword" label="Keyword" density="compact" variant="outlined"
                        hide-details placeholder="title / location / link" />

                    <v-btn size="x-small" variant="text" class="justify-start"
                        style="padding-left: 0; min-height: 24px; color: rgba(var(--v-theme-on-surface), 0.72);"
                        @click="showAdvanced = !showAdvanced">
                        <v-icon size="14" class="mr-1">{{ showAdvanced ? 'mdi-chevron-down' : 'mdi-chevron-right' }}</v-icon>
                        Advanced
                    </v-btn>

                    <v-expand-transition>
                        <v-sheet v-show="showAdvanced" class="d-flex flex-column ga-2">
                            <v-select v-model="searchForm.source" :items="dialogSourceItems" label="Source"
                                density="compact" variant="outlined" hide-details clearable />
                            <v-text-field v-model="searchForm.startDate" label="Start Date" density="compact" variant="outlined"
                                type="date" hide-details />
                            <v-text-field v-model="searchForm.endDate" label="End Date" density="compact" variant="outlined"
                                type="date" hide-details />
                        </v-sheet>
                    </v-expand-transition>

                    <v-sheet class="d-flex ga-2 mt-1">
                        <v-btn size="small" color="primary" :loading="searchLoading" @click="runSearch">Search</v-btn>
                        <v-btn size="small" variant="outlined" @click="resetSearch">Reset</v-btn>
                    </v-sheet>

                    <v-sheet class="text-caption text-medium-emphasis mt-2">{{ searchResults.length }} result{{ searchResults.length === 1 ? '' : 's' }}</v-sheet>
                    <v-sheet v-if="searchError" class="text-caption text-error mt-1">{{ searchError }}</v-sheet>

                    <v-list v-if="searchResultEvents.length > 0" density="compact" class="search-result-list mt-2">
                        <v-list-item v-for="ev in searchResultEvents" :key="`search-${ev.id}`"
                            :active="selectedEventId === ev.id" active-color="primary" rounded="lg" class="mb-1 px-2 py-2"
                            @click="onEventClick(ev)">
                            <template #prepend>
                                <v-sheet width="4" rounded class="mr-3" :style="{ background: sourceColorHex(ev.source), minHeight: '40px' }" />
                            </template>
                            <v-sheet class="flex-grow-1 min-width-0">
                                <v-sheet class="d-flex align-center ga-2">
                                    <v-sheet class="text-body-2 font-weight-medium text-truncate">{{ ev.title }}</v-sheet>
                                </v-sheet>
                                <v-sheet class="text-caption text-medium-emphasis mt-1">{{ ev.date }} {{ getEventDisplayTime(ev) }}</v-sheet>
                            </v-sheet>
                        </v-list-item>
                    </v-list>
                </v-sheet>
            </aside>
        </v-sheet>

        <v-dialog v-model="sourceColorDialogOpen" max-width="420">
            <v-card rounded="lg">
                <v-card-title class="text-body-2 font-weight-bold">Edit Source Color</v-card-title>
                <v-card-text>
                    <v-sheet class="text-caption text-medium-emphasis mb-2">Source: {{ colorEditingSource }}</v-sheet>
                    <v-color-picker v-model="colorEditingValue" mode="hexa" hide-inputs elevation="0" />
                </v-card-text>
                <v-card-actions class="justify-end px-4 pb-4">
                    <v-btn size="small" variant="outlined" @click="sourceColorDialogOpen = false">Cancel</v-btn>
                    <v-btn size="small" color="primary" :loading="sourceColorSaving" @click="confirmSourceColor">Confirm</v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>

        <v-snackbar v-model="colorNoticeOpen" timeout="1800" location="bottom right">
            {{ colorNotice }}
        </v-snackbar>

        <v-menu v-model="eventContextMenuOpen" :target="[eventContextMenuX, eventContextMenuY]" location="bottom start">
            <v-list density="compact" min-width="140">
                <v-list-item prepend-icon="mdi-pencil" title="Modify" @click="modifyFromContextMenu" />
            </v-list>
        </v-menu>

        <CalendarEventDialog v-model="dialogOpen" :event="editingEvent" :default-date="dialogDefaultDate"
            @submit="saveEvent" />
    </v-sheet>
</template>

<script setup lang="ts">
    import CalendarGrid from '@/components/calendar/CalendarGrid.vue'
    import CalendarEventPanel from '@/components/calendar/CalendarEventPanel.vue'
    import CalendarEventDialog from '@/components/calendar/CalendarEventDialog.vue'
    import {
        createCalendarEvent,
        deleteCalendarEvent,
        getCalendarEventById,
        getCalendarEvents,
        getCalendarSources,
        searchCalendarEvents,
        updateCalendarSource,
        updateCalendarEvent,
    } from '@/api/calendar'
    import type { CalEvent, CalendarCell } from '@/types/calendar'
    import {
        fromDateKey,
        getEventDisplayTime,
        getEventEndTime,
        getEventStartTime,
        getEventsForDate,
        toDateKey,
        toUnixSecondsByDateKey,
    } from '@/utils/calendar'
    const SEARCH_MIN_DATE = '0000-01-01'
    const SEARCH_MAX_DATE = '9999-12-31'
    const ALL_EVENTS_START_TIME = 0
    const ALL_EVENTS_END_TIME = 4102444799
    const CALENDAR_PAGE_STORAGE_KEY = 'calendar:index:state:v1'
    const CALENDAR_POLL_INTERVAL_MS = 30000
    const CALENDAR_POLL_INTERVAL_GUARD_MS = 28000
    const CALENDAR_SCROLL_REFRESH_DEBOUNCE_MS = 320

    interface CalendarPagePersistedState {
        viewStartDate: string
        searchForm: {
            keyword: string
            source: string
            startDate: string
            endDate: string
        }
        hasSearched: boolean
        showAdvanced: boolean
        searchRailCollapsed: boolean
        activeSource: CalEvent['source'] | null
        highlightedSources: CalEvent['source'][]
        selectedCellDateKey: string | null
        selectedEventId: number | null
    }

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
    const sourceScopedEvents = ref<CalEvent[]>([])
    const searchResults = ref<CalEvent[]>([])
    const selectedCell = ref<CalendarCell | null>(null)
    const selectedEventId = ref<number | null>(null)
    const activeSource = ref<CalEvent['source'] | null>(null)
    const sourceCatalog = ref<{ id: number; title: string; isVisible: boolean; colorHex: string }[]>([])

    const searchForm = reactive({
        keyword: '',
        source: '',
        startDate: SEARCH_MIN_DATE,
        endDate: SEARCH_MAX_DATE,
    })
    const searchLoading = ref(false)
    const searchError = ref('')
    const hasSearched = ref(false)
    const showAdvanced = ref(false)
    const searchRailCollapsed = ref(false)

    const dialogOpen = ref(false)
    const editingEvent = ref<CalEvent | null>(null)
    const dialogDefaultDate = ref('')
    const pendingEventPatches = ref<Record<number, { form: Omit<CalEvent, 'id'>; expiresAt: number }>>({})
    const eventContextMenuOpen = ref(false)
    const eventContextMenuEvent = ref<CalEvent | null>(null)
    const eventContextMenuX = ref(0)
    const eventContextMenuY = ref(0)
    const lastWheelAt = ref(0)
    const sourceColorDialogOpen = ref(false)
    const colorEditingSource = ref('')
    const colorEditingValue = ref('#3b82f6')
    const sourceColorSaving = ref(false)
    const colorNotice = ref('')
    const colorNoticeOpen = ref(false)
    const persistenceReady = ref(false)
    const calendarPollTimer = ref<ReturnType<typeof window.setInterval> | null>(null)
    const calendarScrollRefreshTimer = ref<ReturnType<typeof window.setTimeout> | null>(null)
    const calendarWheelScrolling = ref(false)
    let sourceEventsRequestToken = 0
    let visibleEventsRequestToken = 0

    type CalendarPollingWindow = Window & {
        __calendarIndexPollTimer__?: ReturnType<typeof window.setInterval> | null
        __calendarIndexPollLastAt__?: number
        __calendarIndexPollInFlight__?: boolean
    }

    const miniHeaders = ['S', 'M', 'T', 'W', 'T', 'F', 'S']
    const sourceOptions = computed<{ value: string; label: string }[]>(() => {
        const seen = new Set<string>()
        const options: { value: string; label: string }[] = []

        // Use backend source catalog as the primary source list (full list, not current month only).
        sourceCatalog.value.forEach(item => {
            const title = `${item.title ?? ''}`.trim()
            if (!title || seen.has(title)) return
            seen.add(title)
            options.push({ value: title, label: title })
        })

        // Fallback: include sources found in loaded events if backend catalog missed any.
        events.value.forEach(item => {
            const source = `${item.source ?? ''}`.trim()
            if (!source || seen.has(source)) return
            seen.add(source)
            options.push({ value: source, label: source })
        })

        return options
    })
    const dialogSourceItems = computed(() => sourceOptions.value.map(item => ({ title: item.label, value: item.value })))

    const sourceColorMap = computed(() => {
        const map = new Map<string, string>()
        sourceCatalog.value.forEach(item => map.set(item.title, item.colorHex))
        return map
    })

    const highlightedSources = ref(new Set<CalEvent['source']>())

    watch(sourceOptions, (items) => {
        const prev = new Set(highlightedSources.value)
        const next = new Set<CalEvent['source']>()
        const availableSources = new Set(items.map(item => item.value))

        items.forEach(item => {
            const sourceMeta = sourceCatalog.value.find(source => source.title === item.value)
            if (prev.size === 0) {
                if (sourceMeta?.isVisible ?? true) next.add(item.value)
                return
            }

            if (prev.has(item.value)) next.add(item.value)
        })

        highlightedSources.value = next

        if (activeSource.value && !availableSources.has(activeSource.value)) {
            activeSource.value = null
            sourceEventsRequestToken += 1
            sourceScopedEvents.value = []
        }

        if (searchForm.source && !availableSources.has(searchForm.source)) {
            searchForm.source = ''
        }
    }, { immediate: true })

    const sourceHighlighted = (source: CalEvent['source']) => highlightedSources.value.has(source)

    const sourceColorHex = (source: string) =>
        sourceColorMap.value.get(source)
        ?? '#2563eb'

    const resolvedSourceColorMap = computed<Record<string, string>>(() => {
        const out: Record<string, string> = {}
        sourceOptions.value.forEach(item => {
            out[item.value] = sourceColorHex(item.value)
        })
        return out
    })

    const showColorNotice = (message: string) => {
        colorNotice.value = message
        colorNoticeOpen.value = true
    }

    const openSourceColorDialog = (source: string) => {
        colorEditingSource.value = source
        colorEditingValue.value = sourceColorHex(source)
        sourceColorDialogOpen.value = true
    }

    const toggleSourceHighlight = async (source: CalEvent['source']) => {
        const prev = new Set(highlightedSources.value)
        const next = new Set(prev)
        if (next.has(source)) next.delete(source)
        else next.add(source)

        const sourceMeta = sourceCatalog.value.find(item => item.title === source)
        if (!sourceMeta) return

        const nextVisible = next.has(source)
        try {
            const updated = await updateCalendarSource(sourceMeta.id, { is_visible: nextVisible })
            sourceMeta.isVisible = updated.is_visible
            sourceMeta.colorHex = `${updated.color ?? ''}`.trim() || sourceMeta.colorHex
            highlightedSources.value = updated.is_visible
                ? new Set([...prev, source])
                : new Set(Array.from(prev).filter(item => item !== source))
        } catch (error) {
            highlightedSources.value = prev
            console.error(error)
            searchError.value = 'Update source visibility failed.'
        }
    }

    const confirmSourceColor = async () => {
        const source = colorEditingSource.value
        const nextHex = `${colorEditingValue.value}`
        if (!source) return

        const sourceMeta = sourceCatalog.value.find(item => item.title === source)
        if (!sourceMeta) {
            searchError.value = `Source ${source} is not managed by backend. Refresh source list first.`
            return
        }

        sourceColorSaving.value = true
        try {
            const updated = await updateCalendarSource(sourceMeta.id, { color: nextHex })
            sourceMeta.colorHex = `${updated.color ?? ''}`.trim() || sourceMeta.colorHex
            sourceMeta.isVisible = updated.is_visible
            sourceColorDialogOpen.value = false
            showColorNotice(`Updated ${source} color.`)
        } catch (error) {
            console.error(error)
            searchError.value = 'Update source color failed.'
        } finally {
            sourceColorSaving.value = false
        }
    }

    const toggleSourceSelection = (source: CalEvent['source']) => {
        const nextSource = activeSource.value === source ? null : source
        activeSource.value = nextSource
        if (!nextSource) {
            sourceEventsRequestToken += 1
            sourceScopedEvents.value = []
            return
        }
        void loadSourceScopedEvents(nextSource)
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
    const searchResultEvents = computed(() =>
        [...searchResults.value].sort((a, b) => {
            const dateCmp = a.date.localeCompare(b.date)
            return dateCmp !== 0 ? dateCmp : getEventStartTime(a).localeCompare(getEventStartTime(b))
        })
    )

    const buildSearchQuery = () => {
        const query: { start_time?: number; end_time?: number; source?: string; key_word?: string } = {}

        const keyword = searchForm.keyword.trim()
        if (keyword) query.key_word = keyword

        const source = `${searchForm.source ?? ''}`.trim()
        if (source) query.source = source

        const startDate = searchForm.startDate
        const endDate = searchForm.endDate

        query.start_time = startDate ? toUnixSecondsByDateKey(startDate, '00:00') : 0
        query.end_time = endDate ? toUnixSecondsByDateKey(endDate, '23:59') + 59 : ALL_EVENTS_END_TIME

        if (
            !query.key_word
            && !query.source
            && !startDate
            && !endDate
        ) return null

        return query
    }

    const runSearch = async (silent = false): Promise<boolean> => {
        hasSearched.value = true
        searchLoading.value = true
        if (!silent) searchError.value = ''
        try {
            const query = buildSearchQuery()
            if (!query) {
                if (!silent) searchError.value = 'Please enter at least one search condition.'
                searchResults.value = []
                return false
            }
            searchResults.value = applyPendingEventPatches(await searchCalendarEvents(query))
            return true
        } catch (error) {
            if (!silent) {
                searchError.value = 'Search failed. Please check backend/API config.'
            }
            console.error(error)
            return false
        } finally {
            searchLoading.value = false
        }
    }

    const resetSearch = async () => {
        searchForm.keyword = ''
        searchForm.source = ''
        searchForm.startDate = SEARCH_MIN_DATE
        searchForm.endDate = SEARCH_MAX_DATE
        showAdvanced.value = false
        searchError.value = ''
        hasSearched.value = false
        searchResults.value = []
    }

    const loadSourceScopedEvents = async (source: CalEvent['source'], silent = false) => {
        const normalizedSource = `${source ?? ''}`.trim()
        if (!normalizedSource) {
            sourceEventsRequestToken += 1
            sourceScopedEvents.value = []
            return
        }

        const requestToken = ++sourceEventsRequestToken
        if (!silent) searchError.value = ''

        try {
            const rows = await searchCalendarEvents({
                source: normalizedSource,
                start_time: ALL_EVENTS_START_TIME,
                end_time: ALL_EVENTS_END_TIME,
            })
            if (requestToken !== sourceEventsRequestToken) return

            sourceScopedEvents.value = applyPendingEventPatches(rows).filter(item => item.source === normalizedSource)
        } catch (error) {
            if (requestToken !== sourceEventsRequestToken) return

            console.error(error)
            sourceScopedEvents.value = []
            if (!silent) searchError.value = 'Load source events failed. Please check backend/API config.'
        }
    }

    const loadSources = async () => {
        try {
            const rows = await getCalendarSources()
            sourceCatalog.value = rows.map(row => ({
                id: row.id,
                title: row.title,
                isVisible: row.is_visible,
                colorHex: `${row.color ?? ''}`.trim() || '#2563eb',
            }))
        } catch (error) {
            console.error(error)
            sourceCatalog.value = []
        }
    }

    const loadVisibleEvents = async (silent = false) => {
        const requestToken = ++visibleEventsRequestToken
        const start = visibleStart.value
        const end = visibleEnd.value
        if (!silent) searchError.value = ''
        try {
            const rows = await getCalendarEvents({
                start,
                end,
            })
            if (requestToken !== visibleEventsRequestToken) return
            events.value = applyPendingEventPatches(rows)
        } catch (error) {
            if (requestToken !== visibleEventsRequestToken) return
            console.error(error)
            if (!silent) searchError.value = 'Load calendar events failed. Please check backend/API config.'
        }
    }

    const clearCalendarScrollRefreshTimer = () => {
        if (typeof window === 'undefined') return
        if (!calendarScrollRefreshTimer.value) return
        window.clearTimeout(calendarScrollRefreshTimer.value)
        calendarScrollRefreshTimer.value = null
    }

    const cancelCalendarScrollRefresh = () => {
        clearCalendarScrollRefreshTimer()
        calendarWheelScrolling.value = false
    }

    const scheduleCalendarScrollRefresh = (silent = true) => {
        if (typeof window === 'undefined') {
            void loadVisibleEvents(silent)
            return
        }

        calendarWheelScrolling.value = true
        clearCalendarScrollRefreshTimer()
        calendarScrollRefreshTimer.value = window.setTimeout(() => {
            calendarScrollRefreshTimer.value = null
            calendarWheelScrolling.value = false
            void loadVisibleEvents(silent)
        }, CALENDAR_SCROLL_REFRESH_DEBOUNCE_MS)
    }

    const pollCalendarVisibleEvents = async () => {
        if (typeof window === 'undefined') return
        const pollingWindow = window as CalendarPollingWindow
        const now = Date.now()
        const lastAt = pollingWindow.__calendarIndexPollLastAt__ ?? 0

        // Guard against duplicated poll timers (e.g. HMR / remount side effects).
        if (now - lastAt < CALENDAR_POLL_INTERVAL_GUARD_MS) return
        if (pollingWindow.__calendarIndexPollInFlight__) return
        if (calendarWheelScrolling.value || calendarScrollRefreshTimer.value) return

        pollingWindow.__calendarIndexPollInFlight__ = true
        try {
            await loadVisibleEvents(true)
            pollingWindow.__calendarIndexPollLastAt__ = Date.now()
        } finally {
            pollingWindow.__calendarIndexPollInFlight__ = false
        }
    }

    const stopCalendarPolling = () => {
        if (typeof window === 'undefined') return
        const pollingWindow = window as CalendarPollingWindow

        if (calendarPollTimer.value) {
            window.clearInterval(calendarPollTimer.value)
        }

        if (pollingWindow.__calendarIndexPollTimer__) {
            window.clearInterval(pollingWindow.__calendarIndexPollTimer__)
            pollingWindow.__calendarIndexPollTimer__ = null
        }

        calendarPollTimer.value = null
    }

    const startCalendarPolling = () => {
        if (typeof window === 'undefined') return
        const pollingWindow = window as CalendarPollingWindow
        stopCalendarPolling()
        calendarPollTimer.value = window.setInterval(() => {
            void pollCalendarVisibleEvents()
        }, CALENDAR_POLL_INTERVAL_MS)

        pollingWindow.__calendarIndexPollTimer__ = calendarPollTimer.value
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
        selectedCell.value ? getEventsForDate(visibleRangeEvents.value, selectedCell.value.dateKey) : []
    )

    const panelEvents = computed(() => {
        if (activeSource.value) {
            return [...sourceScopedEvents.value]
                .filter(e => e.source === activeSource.value)
                .sort((a, b) => {
                    const dateCmp = a.date.localeCompare(b.date)
                    return dateCmp !== 0 ? dateCmp : getEventStartTime(a).localeCompare(getEventStartTime(b))
                })
        }

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

    const panelSubtitle = computed(() => '')

    const selectedEventDetail = computed(() => {
        if (!selectedEventId.value) return null
        return (
            events.value.find(ev => ev.id === selectedEventId.value)
            ?? sourceScopedEvents.value.find(ev => ev.id === selectedEventId.value)
            ?? null
        )
    })

    const prevMonth = () => {
        cancelCalendarScrollRefresh()
        shiftVisibleMonth(-1)
    }

    const nextMonth = () => {
        cancelCalendarScrollRefresh()
        shiftVisibleMonth(1)
    }

    const goToday = () => {
        cancelCalendarScrollRefresh()
        const now = new Date()
        viewStartDate.value = startOfWeek(new Date(now.getFullYear(), now.getMonth(), 1))
        const cell = cells.value.find(c => c.dateKey === todayKey)
        if (cell) selectedCell.value = cell
    }

    const onCellClick = (cell: CalendarCell) => {
        selectedCell.value = cell
        selectedEventId.value = null
    }

    const onEventClick = async (ev: CalEvent) => {
        selectedEventId.value = ev.id
        const eventDate = fromDateKey(ev.date)
        const inCurrentView = cells.value.some(c => c.dateKey === ev.date)
        if (!inCurrentView) {
            cancelCalendarScrollRefresh()
            viewStartDate.value = startOfWeek(new Date(eventDate.getFullYear(), eventDate.getMonth(), 1))
            await nextTick()
        }
        const cell = cells.value.find(c => c.dateKey === ev.date)
        if (cell) selectedCell.value = cell
    }

    const onCalendarWheel = (event: WheelEvent) => {
        if (Math.abs(event.deltaY) < 10) return

        const now = Date.now()
        if (now - lastWheelAt.value < 220) return
        lastWheelAt.value = now
        scheduleCalendarScrollRefresh(true)

        if (event.deltaY > 0) {
            viewStartDate.value = addDays(viewStartDate.value, 7)
            return
        }
        viewStartDate.value = addDays(viewStartDate.value, -7)
    }

    const sourceChipStyle = (source: CalEvent['source']) => {
        const color = sourceColorHex(source)
        const selected = activeSource.value === source
        return sourceHighlighted(source)
            ? {
                '--strip-accent': color,
                background: 'transparent',
                color: 'rgba(var(--v-theme-on-surface), 0.9)',
                borderColor: selected ? `color-mix(in srgb, ${color} 45%, rgba(var(--v-theme-on-surface), 0.3))` : 'rgba(var(--v-theme-on-surface), 0.18)',
                boxShadow: selected ? `inset 0 0 0 1px color-mix(in srgb, ${color} 50%, transparent)` : 'none'
            }
            : {
                '--strip-accent': color,
                background: 'transparent',
                color: 'rgba(var(--v-theme-on-surface), 0.78)',
                borderColor: selected ? `color-mix(in srgb, ${color} 38%, rgba(var(--v-theme-on-surface), 0.24))` : 'rgba(var(--v-theme-on-surface), 0.12)',
                boxShadow: selected ? `inset 0 0 0 1px color-mix(in srgb, ${color} 42%, transparent)` : 'none'
            }
    }

    const persistCalendarPageState = () => {
        if (typeof window === 'undefined') return

        const payload: CalendarPagePersistedState = {
            viewStartDate: toDateKey(viewStartDate.value),
            searchForm: {
                keyword: searchForm.keyword,
                source: searchForm.source,
                startDate: searchForm.startDate,
                endDate: searchForm.endDate,
            },
            hasSearched: hasSearched.value,
            showAdvanced: showAdvanced.value,
            searchRailCollapsed: searchRailCollapsed.value,
            activeSource: activeSource.value,
            highlightedSources: Array.from(highlightedSources.value),
            selectedCellDateKey: selectedCell.value?.dateKey ?? null,
            selectedEventId: selectedEventId.value,
        }

        localStorage.setItem(CALENDAR_PAGE_STORAGE_KEY, JSON.stringify(payload))
    }

    const restoreCalendarPageState = () => {
        if (typeof window === 'undefined') return

        const raw = localStorage.getItem(CALENDAR_PAGE_STORAGE_KEY)
        if (!raw) return

        try {
            const parsed = JSON.parse(raw) as Partial<CalendarPagePersistedState>

            if (typeof parsed.viewStartDate === 'string' && parsed.viewStartDate) {
                viewStartDate.value = startOfWeek(fromDateKey(parsed.viewStartDate))
            }

            const savedForm = parsed.searchForm
            if (savedForm) {
                searchForm.keyword = `${savedForm.keyword ?? ''}`
                searchForm.source = `${savedForm.source ?? ''}`
                searchForm.startDate = `${savedForm.startDate ?? SEARCH_MIN_DATE}`
                searchForm.endDate = `${savedForm.endDate ?? SEARCH_MAX_DATE}`
            }

            hasSearched.value = !!parsed.hasSearched
            showAdvanced.value = !!parsed.showAdvanced
            searchRailCollapsed.value = !!parsed.searchRailCollapsed
            activeSource.value = parsed.activeSource ?? null

            const savedHighlights = Array.isArray(parsed.highlightedSources) ? parsed.highlightedSources : []
            highlightedSources.value = new Set(savedHighlights)

            selectedEventId.value = typeof parsed.selectedEventId === 'number' ? parsed.selectedEventId : null

            const selectedDateKey = typeof parsed.selectedCellDateKey === 'string' ? parsed.selectedCellDateKey : ''
            if (selectedDateKey) {
                selectedCell.value = cells.value.find(c => c.dateKey === selectedDateKey) ?? null
            }
        } catch (error) {
            console.error(error)
            localStorage.removeItem(CALENDAR_PAGE_STORAGE_KEY)
        }
    }

    const openCreate = (date: string) => {
        editingEvent.value = null
        dialogDefaultDate.value = date
        dialogOpen.value = true
    }

    const openEdit = (ev: CalEvent) => {
        eventContextMenuOpen.value = false
        eventContextMenuEvent.value = null
        editingEvent.value = ev
        dialogOpen.value = true
    }

    const openEventContextMenu = (payload: { event: CalEvent; mouseEvent: MouseEvent }) => {
        eventContextMenuEvent.value = payload.event
        eventContextMenuX.value = payload.mouseEvent.clientX
        eventContextMenuY.value = payload.mouseEvent.clientY
        eventContextMenuOpen.value = true
        selectedEventId.value = payload.event.id
    }

    const modifyFromContextMenu = () => {
        const targetEvent = eventContextMenuEvent.value
        eventContextMenuOpen.value = false
        eventContextMenuEvent.value = null
        if (!targetEvent) return
        openEdit(targetEvent)
    }

    const applyEventFormToCollections = (eventId: number, form: Omit<CalEvent, 'id'>) => {
        const mergeEvent = (item: CalEvent): CalEvent =>
            item.id === eventId
                ? {
                    ...item,
                    ...form,
                    id: eventId,
                }
                : item

        events.value = events.value.map(mergeEvent)
            sourceScopedEvents.value = sourceScopedEvents.value.map(mergeEvent)
    }

    const mergeEventPatch = (item: CalEvent): CalEvent => {
        const patch = pendingEventPatches.value[item.id]
        if (!patch) return item
        if (patch.expiresAt <= Date.now()) {
            delete pendingEventPatches.value[item.id]
            return item
        }
        return {
            ...item,
            ...patch.form,
            id: item.id,
        }
    }

    const applyPendingEventPatches = (items: CalEvent[]) => items.map(mergeEventPatch)

    const replaceEventInCollections = (nextEvent: CalEvent) => {
        const normalizedEvent = mergeEventPatch(nextEvent)
        const replaceEvent = (item: CalEvent): CalEvent => item.id === normalizedEvent.id ? normalizedEvent : item
        events.value = events.value.map(replaceEvent)
        sourceScopedEvents.value = sourceScopedEvents.value.map(replaceEvent)
    }

    const matchesEventPatch = (event: CalEvent, form: Omit<CalEvent, 'id'>) =>
        event.title === form.title
        && event.date === form.date
        && (event.startTime ?? '') === (form.startTime ?? '')
        && (event.endTime ?? '') === (form.endTime ?? '')
        && (event.description ?? '') === (form.description ?? '')
        && (event.location ?? '') === (form.location ?? '')
        && (event.link ?? '') === (form.link ?? '')
        && (event.color ?? '') === (form.color ?? '')

    const wait = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))
    const PATCH_TTL_MS = 10000

    const reconcileUpdatedEvent = async (eventId: number, form: Omit<CalEvent, 'id'>) => {
        for (const delay of [150, 400, 900, 1500, 2500, 4000]) {
            await wait(delay)
            const latest = await getCalendarEventById(eventId)
            if (!latest) continue
            if (!matchesEventPatch(latest, form)) continue
            delete pendingEventPatches.value[eventId]
            replaceEventInCollections(latest)
            return
        }
        delete pendingEventPatches.value[eventId]
        await loadVisibleEvents(true)
    }

    const refreshCalendarData = async () => {
        await loadVisibleEvents(true)
        if (activeSource.value) {
            await loadSourceScopedEvents(activeSource.value, true)
        }
    }

    const saveEvent = async (form: Omit<CalEvent, 'id'>) => {
        const previousEvents = [...events.value]
        const previousSearchResults = [...searchResults.value]
        try {
            if (editingEvent.value) {
                const editingId = editingEvent.value.id
                pendingEventPatches.value[editingId] = {
                    form: { ...form },
                    expiresAt: Date.now() + PATCH_TTL_MS,
                }
                applyEventFormToCollections(editingId, form)
                await updateCalendarEvent(editingId, form)
                void reconcileUpdatedEvent(editingId, form)
                dialogOpen.value = false
                editingEvent.value = null
                return
            } else {
                const created = await createCalendarEvent(form)
                events.value = [...events.value, created]
                await refreshCalendarData()
            }
            dialogOpen.value = false
            editingEvent.value = null
        } catch (error) {
            if (editingEvent.value) delete pendingEventPatches.value[editingEvent.value.id]
            events.value = previousEvents
            searchResults.value = previousSearchResults
            console.error(error)
            searchError.value = 'Save failed. Please check backend response.'
        }
    }

    const deleteEvent = async (ev: CalEvent) => {
        try {
            await deleteCalendarEvent(ev.id)
            await refreshCalendarData()
            if (selectedEventId.value === ev.id) selectedEventId.value = null
        } catch (error) {
            console.error(error)
            searchError.value = 'Delete failed. Please check backend response.'
        }
    }

    watch(cells, () => {
        const currentSelectedCell = selectedCell.value
        if (!currentSelectedCell) return
        if (cells.value.some(c => c.dateKey === currentSelectedCell.dateKey)) return
        selectedCell.value = null
    }, { immediate: true })

    watch(
        [
            viewStartDate,
            events,
            searchResults,
            activeSource,
            highlightedSourceList,
            selectedCell,
            selectedEventId,
            hasSearched,
            showAdvanced,
            searchRailCollapsed,
            () => searchForm.keyword,
            () => searchForm.source,
            () => searchForm.startDate,
            () => searchForm.endDate,
        ],
        () => {
            if (!persistenceReady.value) return
            persistCalendarPageState()
        },
        { deep: true }
    )

    watch([visibleStart, visibleEnd], () => {
        if (calendarWheelScrolling.value || calendarScrollRefreshTimer.value) return
        loadVisibleEvents(true)
    })

    onMounted(async () => {
        await loadSources()
        restoreCalendarPageState()
        await loadVisibleEvents()
        if (activeSource.value) {
            await loadSourceScopedEvents(activeSource.value, true)
        }
        persistenceReady.value = true
        persistCalendarPageState()
        startCalendarPolling()
    })

    onBeforeUnmount(() => {
        cancelCalendarScrollRefresh()
        stopCalendarPolling()
    })
</script>

<style scoped>
    .source-chip {
        width: 100%;
        min-height: 30px;
        justify-content: flex-start;
        position: relative;
        font-weight: 500;
        border-radius: 8px;
        padding-left: 8px;
    }

    .source-chip :deep(.v-chip__content) {
        width: 100%;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .search-result-list {
        max-height: 320px;
        overflow-y: auto;
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        border-radius: 10px;
        background: rgba(var(--v-theme-surface), 0.5);
    }

    .event-details-card {
        position: absolute;
        right: 12px;
        top: 44px;
        width: 380px;
        max-width: calc(100% - 24px);
        max-height: calc(100% - 56px);
        overflow: auto;
        padding: 10px 12px;
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        background: rgba(var(--v-theme-surface), 0.96);
        backdrop-filter: blur(6px);
        z-index: 3;
    }

    .event-detail-row {
        display: flex;
        gap: 8px;
        font-size: 12px;
        line-height: 1.4;
        margin-top: 6px;
    }

    .event-detail-link {
        color: rgb(var(--v-theme-primary));
        text-decoration: none;
        word-break: break-all;
    }

    .event-detail-link:hover {
        text-decoration: underline;
    }

    .mini-day-btn {
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        border-radius: 6px;
        background: transparent;
        color: rgba(var(--v-theme-on-surface), 0.88);
        font-size: 10px;
        height: 24px;
        cursor: pointer;
    }

    .mini-day-btn.muted {
        opacity: 0.4;
    }

    .mini-day-btn.today {
        border-color: rgb(var(--v-theme-primary));
    }

    .mini-day-btn.active {
        background: rgba(var(--v-theme-primary), 0.15);
        border-color: rgb(var(--v-theme-primary));
    }
</style>
