<template>
    <v-sheet color="surface" class="calendar-workspace d-flex flex-column h-100 overflow-hidden"
        :style="calendarWorkspaceStyle">
        <v-sheet class="d-flex flex-grow-1 min-height-0 overflow-hidden">
            <v-sheet width="250" min-width="250" max-width="250"
                class="d-flex flex-column min-height-0 overflow-hidden">
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
                            <span v-for="h in miniHeaders" :key="h" class="mini-weekday">{{ h }}</span>
                            <button v-for="c in cells" :key="`mini-${c.dateKey}`" class="mini-day-btn"
                                :class="{ muted: !c.currentMonth, today: c.isToday, active: selectedCell?.dateKey === c.dateKey }"
                                @click="onCellClick(c)">
                                {{ c.day }}
                            </button>
                        </v-sheet>
                    </v-sheet>

                    <v-sheet class="pa-3 border-b">
                        <v-sheet class="calendar-section-label mb-2">Source</v-sheet>
                        <v-sheet class="d-flex flex-column ga-2">
                            <v-chip v-for="src in sourceOptions" :key="src.value" class="source-chip" size="small" label
                                :variant="activeSource === src.value ? 'flat' : 'tonal'"
                                :style="sourceChipStyle(src.value)" @click="toggleSourceSelection(src.value)">
                                <v-sheet color="transparent" class="d-flex align-center w-100 ga-2">
                                    <v-sheet class="flex-shrink-0" width="4" rounded="pill"
                                        style="align-self: stretch; margin: 2px 0; background: var(--strip-accent);" />
                                    <span>{{ src.label }}</span>
                                    <v-btn icon size="x-small" variant="text" class="source-action-btn"
                                        style="margin-left: auto; margin-right: -4px;"
                                        :aria-label="sourceHighlighted(src.value) ? 'Hide highlight' : 'Show highlight'"
                                        @click.stop="toggleSourceHighlight(src.value)">
                                        <v-icon size="14">{{ sourceHighlighted(src.value) ? 'mdi-eye' : 'mdi-eye-off'
                                            }}</v-icon>
                                    </v-btn>
                                    <v-btn icon size="x-small" variant="text" class="source-action-btn"
                                        style="margin-right: -4px;" aria-label="Edit source color"
                                        @click.stop="openSourceColorDialog(src.value)">
                                        <v-icon size="14">mdi-palette</v-icon>
                                    </v-btn>
                                </v-sheet>
                            </v-chip>
                        </v-sheet>
                    </v-sheet>
                </v-sheet>

                <CalendarEventPanel embedded :show-header="false" :events="panelEvents"
                    :selected-event-id="selectedEventId" :source-color-map="resolvedSourceColorMap"
                    @select="onEventClick" @edit="onEventClick" @delete="deleteEvent"
                    @contextmenu="openEventContextMenu" />
            </v-sheet>

            <v-sheet
                class="calendar-center-panel flex-grow-1 d-flex flex-column min-width-0 min-height-0 overflow-hidden">
                <v-sheet class="calendar-toolbar px-4 py-2 border-b d-flex align-center justify-end flex-shrink-0">
                    <v-sheet color="transparent" class="calendar-toolbar-actions d-flex align-center ga-2">
                        <v-btn icon size="small" variant="text" @click="goToday">
                            <v-icon size="16">mdi-calendar-today</v-icon>
                            <v-tooltip activator="parent" location="bottom">Today</v-tooltip>
                        </v-btn>
                        <v-btn icon size="small" variant="text" @click="startInlineCreate">
                            <v-icon size="16">mdi-plus</v-icon>
                            <v-tooltip activator="parent" location="bottom">New Event</v-tooltip>
                        </v-btn>
                        <v-btn icon size="small" variant="text" @click="searchRailCollapsed = !searchRailCollapsed">
                            <v-icon size="14">{{ searchRailCollapsed ? 'mdi-dock-right' : 'mdi-dock-window' }}</v-icon>
                            <v-tooltip activator="parent" location="bottom">{{ searchRailCollapsed ? 'Show right panel'
                                :
                                'Hide right panel' }}</v-tooltip>
                        </v-btn>
                    </v-sheet>
                </v-sheet>

                <section
                    class="calendar-grid-shell flex-grow-1 d-flex flex-column min-width-0 min-height-0 border-b"
                    style="overflow: hidden; position: relative;" @wheel.prevent="onCalendarWheel">
                    <CalendarGrid :cells="cells" :events="displayEvents" :selected-cell="selectedCell"
                        :source-color-map="resolvedSourceColorMap" :selected-event-id="selectedEventId"
                        @cell-click="onCellClick" @event-click="onEventClick" @event-context-menu="openEventContextMenu"
                        @event-drop="moveEventToDate" />
                </section>
            </v-sheet>


            <aside v-if="!searchRailCollapsed" class="calendar-right-panel d-flex flex-column">
                <template v-if="selectedEventDetail">
                    <v-sheet class="px-3 py-2 border-b d-flex align-center justify-space-between ga-2">
                        <v-sheet class="d-flex align-center ga-2 min-width-0">
                            <v-sheet width="8" height="8" rounded="circle" class="flex-shrink-0"
                                :style="{ background: selectedEventColor }" />
                            <span class="text-body-2 font-weight-bold text-truncate">
                                {{ selectedEventIsDraft ? 'New Event' : 'Event Details' }}
                            </span>
                        </v-sheet>
                        <v-btn icon size="x-small" variant="text" @click="closeSelectedEventDetail">
                            <v-icon size="14">mdi-close</v-icon>
                        </v-btn>
                    </v-sheet>

                    <v-sheet class="calendar-event-detail-body">
                        <template v-if="selectedEventEditable">
                            <v-text-field v-model="eventDetailForm.title" class="calendar-detail-title"
                                density="compact" variant="plain" hide-details placeholder="Untitled event"
                                :autofocus="selectedEventIsDraft" :loading="eventDetailSaving"
                                @blur="saveSelectedEventDetail" />
                            <v-sheet v-if="selectedEventIsDraft" class="calendar-detail-draft-hint">
                                Add a title to create this event.
                            </v-sheet>

                            <v-sheet class="calendar-detail-property">
                                <v-icon class="calendar-detail-property-icon" size="13">mdi-calendar-outline</v-icon>
                                <v-sheet class="calendar-detail-property-content">
                                    <span class="calendar-detail-label">Date</span>
                                    <v-text-field v-model="eventDetailForm.date" class="calendar-detail-field"
                                        density="compact" variant="outlined" rounded="lg" type="date" hide-details
                                        @blur="saveSelectedEventDetail" />
                                </v-sheet>
                            </v-sheet>

                            <v-sheet class="calendar-detail-property">
                                <v-icon class="calendar-detail-property-icon" size="13">mdi-clock-outline</v-icon>
                                <v-sheet class="calendar-detail-property-content">
                                    <span class="calendar-detail-label">Time</span>
                                    <v-sheet color="transparent" class="d-flex align-center ga-2">
                                        <v-text-field :model-value="eventDetailForm.startTime"
                                            class="calendar-detail-field" density="compact" variant="outlined"
                                            rounded="lg" type="time" :max="eventDetailForm.endTime || undefined"
                                            hide-details @update:model-value="updateEventStartTime"
                                            @blur="saveSelectedEventDetail" />
                                        <span class="calendar-detail-time-separator">to</span>
                                        <v-text-field :model-value="eventDetailForm.endTime"
                                            class="calendar-detail-field" density="compact" variant="outlined"
                                            rounded="lg" type="time" :min="eventDetailForm.startTime || undefined"
                                            hide-details @update:model-value="updateEventEndTime"
                                            @blur="saveSelectedEventDetail" />
                                    </v-sheet>
                                </v-sheet>
                            </v-sheet>

                            <v-sheet class="calendar-detail-property">
                                <v-icon class="calendar-detail-property-icon" size="13">mdi-map-marker-outline</v-icon>
                                <v-sheet class="calendar-detail-property-content">
                                    <span class="calendar-detail-label">Location</span>
                                    <v-text-field v-model="eventDetailForm.location" class="calendar-detail-field"
                                        density="compact" variant="outlined" rounded="lg" hide-details
                                        placeholder="Add location" @blur="saveSelectedEventDetail" />
                                </v-sheet>
                            </v-sheet>

                            <v-sheet class="calendar-detail-property">
                                <v-icon class="calendar-detail-property-icon" size="13">mdi-link-variant</v-icon>
                                <v-sheet class="calendar-detail-property-content">
                                    <span class="calendar-detail-label">Link</span>
                                    <v-text-field v-model="eventDetailForm.link" class="calendar-detail-field"
                                        density="compact" variant="outlined" rounded="lg" hide-details
                                        placeholder="https://..." @blur="saveSelectedEventDetail" />
                                </v-sheet>
                            </v-sheet>

                            <v-sheet class="calendar-detail-property align-start">
                                <v-icon class="calendar-detail-property-icon mt-2"
                                    size="13">mdi-text-box-outline</v-icon>
                                <v-sheet class="calendar-detail-property-content">
                                    <span class="calendar-detail-label">Description</span>
                                    <v-textarea v-model="eventDetailForm.description" class="calendar-detail-field"
                                        density="compact" variant="outlined" rounded="lg" rows="3" auto-grow
                                        hide-details placeholder="Add notes" @blur="saveSelectedEventDetail" />
                                </v-sheet>
                            </v-sheet>
                        </template>

                        <template v-else>
                            <v-sheet class="calendar-detail-read-title">{{ selectedEventDetail.title }}</v-sheet>

                            <v-sheet class="calendar-detail-property">
                                <v-icon class="calendar-detail-property-icon" size="13">mdi-clock-outline</v-icon>
                                <v-sheet class="calendar-detail-property-content">
                                    <span class="calendar-detail-label">Time</span>
                                    <strong class="calendar-detail-value">{{ selectedEventDetail.date }} {{
                                        getEventDisplayTime(selectedEventDetail) || '-' }}</strong>
                                </v-sheet>
                            </v-sheet>
                            <v-sheet class="calendar-detail-property">
                                <v-icon class="calendar-detail-property-icon" size="13">mdi-map-marker-outline</v-icon>
                                <v-sheet class="calendar-detail-property-content">
                                    <span class="calendar-detail-label">Location</span>
                                    <strong class="calendar-detail-value">{{ selectedEventDetail.location || '-'
                                        }}</strong>
                                </v-sheet>
                            </v-sheet>
                            <v-sheet class="calendar-detail-property">
                                <v-icon class="calendar-detail-property-icon" size="13">mdi-link-variant</v-icon>
                                <v-sheet class="calendar-detail-property-content">
                                    <span class="calendar-detail-label">Link</span>
                                    <a v-if="selectedEventDetail.link" class="event-detail-link"
                                        :href="selectedEventDetail.link" target="_blank" rel="noopener noreferrer">
                                        {{ selectedEventDetail.link }}
                                    </a>
                                    <strong v-else class="calendar-detail-value">-</strong>
                                </v-sheet>
                            </v-sheet>
                            <v-sheet class="calendar-detail-property align-start">
                                <v-icon class="calendar-detail-property-icon mt-1"
                                    size="13">mdi-text-box-outline</v-icon>
                                <v-sheet class="calendar-detail-property-content">
                                    <span class="calendar-detail-label">Description</span>
                                    <strong class="calendar-detail-value">{{ selectedEventDetail.description || '-'
                                        }}</strong>
                                </v-sheet>
                            </v-sheet>
                        </template>

                        <v-divider />

                        <v-sheet class="calendar-detail-meta-row">
                            <span>Source</span>
                            <v-chip size="x-small" label>{{ selectedEventDetail.source }}</v-chip>
                        </v-sheet>
                        <v-sheet class="calendar-detail-meta-row">
                            <span>Color</span>
                            <v-menu v-if="selectedEventEditable" v-model="eventColorMenuOpen" location="top end">
                                <template #activator="{ props: menuProps }">
                                    <v-btn v-bind="menuProps" size="x-small" variant="text"
                                        class="calendar-color-value-btn text-none">
                                        <v-sheet width="10" height="10" rounded="circle"
                                            :style="{ background: selectedEventColor }" />
                                        <strong>{{ selectedEventColorLabel }}</strong>
                                    </v-btn>
                                </template>

                                <v-card rounded="lg" class="calendar-color-menu pa-2" min-width="178">
                                    <v-list density="compact" bg-color="transparent" class="pa-0">
                                        <v-list-item rounded="lg" slim class="calendar-color-list-item"
                                            :disabled="eventColorSaving" @click="setSelectedEventColor(null)">
                                            <template #prepend>
                                                <v-sheet width="14" height="14" rounded="sm"
                                                    :style="{ background: selectedEventDetail ? sourceColorHex(selectedEventDetail.source) : '#4ca8df' }" />
                                            </template>
                                            <v-list-item-title class="text-caption">Source color</v-list-item-title>
                                            <template v-if="!selectedEventOwnColor" #append>
                                                <v-icon size="14">mdi-check</v-icon>
                                            </template>
                                        </v-list-item>
                                        <v-divider class="my-1" />
                                        <v-list-item v-for="option in calendarColorOptions" :key="`event-${option.hex}`"
                                            rounded="lg" slim class="calendar-color-list-item"
                                            :disabled="eventColorSaving" @click="setSelectedEventColor(option.hex)">
                                            <template #prepend>
                                                <v-sheet width="14" height="14" rounded="sm"
                                                    :style="{ background: option.hex }" />
                                            </template>
                                            <v-list-item-title class="text-caption">{{ option.label
                                                }}</v-list-item-title>
                                            <template v-if="selectedEventOwnColor === option.hex" #append>
                                                <v-icon size="14">mdi-check</v-icon>
                                            </template>
                                        </v-list-item>
                                    </v-list>
                                </v-card>
                            </v-menu>
                            <v-sheet v-else color="transparent" class="d-flex align-center ga-2">
                                <v-sheet width="10" height="10" rounded="circle"
                                    :style="{ background: selectedEventColor }" />
                                <strong>{{ selectedEventColorLabel }}</strong>
                            </v-sheet>
                        </v-sheet>
                        <v-sheet v-if="!selectedEventEditable" class="calendar-helper-text">
                            This event is read-only because it was imported from another source.
                        </v-sheet>
                        <v-sheet v-else-if="eventDetailSaving" class="calendar-helper-text">
                            Saving...
                        </v-sheet>
                        <v-sheet v-if="eventDetailError" class="text-caption text-error">
                            {{ eventDetailError }}
                        </v-sheet>
                    </v-sheet>
                </template>

                <template v-else>
                    <v-sheet class="pa-3 d-flex flex-column ga-2">
                        <v-text-field v-model="searchForm.keyword" class="calendar-detail-field calendar-search-field"
                            density="compact" variant="outlined" rounded="lg" hide-details clearable
                            placeholder="Search events" prepend-inner-icon="mdi-magnify" :loading="searchLoading"
                            @click:clear="clearSearch" />
                    </v-sheet>

                    <v-sheet class="px-3 py-2 d-flex flex-column ga-1 min-height-0">
                        <v-sheet v-if="searchForm.keyword.trim()" class="calendar-search-count">{{
                            searchResults.length }} result{{ searchResults.length === 1 ? '' : 's' }}</v-sheet>
                        <v-sheet v-else class="calendar-search-count">
                            Type a keyword to search events.
                        </v-sheet>
                        <v-sheet v-if="searchError" class="text-caption text-error mt-1">{{ searchError }}</v-sheet>

                        <v-list v-if="searchResultEvents.length > 0" density="compact" class="search-result-list mt-1">
                            <v-list-item v-for="ev in searchResultEvents" :key="`search-${ev.id}`"
                                :active="selectedEventId === ev.id" rounded="lg" slim :ripple="false"
                                class="calendar-search-item mb-1 px-2 py-0" @click="onEventClick(ev)">
                                <template #prepend>
                                    <v-sheet width="4" rounded="pill" class="calendar-search-item-strip mr-2"
                                        :style="{ background: sourceColorHex(ev.source) }" />
                                </template>
                                <v-sheet color="transparent" class="flex-grow-1 min-width-0">
                                    <v-sheet color="transparent" class="calendar-search-item-title text-truncate">{{
                                        ev.title }}</v-sheet>
                                    <v-sheet color="transparent" class="calendar-search-item-subtitle">{{
                                        ev.date }} {{
                                            getEventDisplayTime(ev) }}</v-sheet>
                                </v-sheet>
                            </v-list-item>
                        </v-list>
                    </v-sheet>
                </template>
            </aside>
        </v-sheet>

        <v-dialog v-model="sourceColorDialogOpen" max-width="280">
            <v-card rounded="lg">
                <v-card-title class="text-body-2 font-weight-bold">Source Color</v-card-title>
                <v-card-text>
                    <v-sheet class="calendar-helper-text mb-2">Source: {{ colorEditingSource }}</v-sheet>
                    <v-list density="compact" bg-color="transparent" class="pa-0">
                        <v-list-item v-for="option in calendarColorOptions" :key="`source-${option.hex}`" rounded="lg"
                            slim class="calendar-color-list-item" :disabled="sourceColorSaving"
                            @click="setSourceColor(option.hex)">
                            <template #prepend>
                                <v-sheet width="14" height="14" rounded="sm" :style="{ background: option.hex }" />
                            </template>
                            <v-list-item-title class="text-caption">{{ option.label }}</v-list-item-title>
                            <template v-if="colorEditingValue === option.hex" #append>
                                <v-icon size="14">mdi-check</v-icon>
                            </template>
                        </v-list-item>
                    </v-list>
                </v-card-text>
            </v-card>
        </v-dialog>

        <v-snackbar v-model="colorNoticeOpen" timeout="1800" location="bottom right">
            {{ colorNotice }}
        </v-snackbar>

    </v-sheet>
</template>

<script setup lang="ts">
    import { useTheme } from 'vuetify'
    import CalendarGrid from '@/components/calendar/CalendarGrid.vue'
    import CalendarEventPanel from '@/components/calendar/CalendarEventPanel.vue'
    import {
        createCalendarEvent,
        deleteCalendarEvent,
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
        getEventStartTime,
        getEventsForDate,
        toDateKey,
        toUnixSecondsByDateKey,
    } from '@/utils/calendar'
    import { CALENDAR_COLOR_OPTIONS, getCalendarColorLabel, normalizeCalendarColor, normalizeOptionalCalendarColor } from '@/utils/calendarColors'
    const ALL_EVENTS_START_TIME = 0
    const ALL_EVENTS_END_TIME = 4102444799
    const CALENDAR_PAGE_STORAGE_KEY = 'calendar:index:state:v1'
    const CALENDAR_POLL_INTERVAL_MS = 30000
    const CALENDAR_POLL_INTERVAL_GUARD_MS = 28000
    const CALENDAR_SCROLL_REFRESH_DEBOUNCE_MS = 320
    const CALENDAR_WHEEL_STEP_DELTA = 90
    const CALENDAR_WHEEL_LINE_DELTA = 32
    const CALENDAR_WHEEL_PAGE_DELTA = 240
    const CALENDAR_MAX_WHEEL_STEPS_PER_FRAME = 6
    const CALENDAR_WHEEL_ACCUMULATOR_RESET_MS = 260
    const theme = useTheme()

    interface CalendarPagePersistedState {
        viewStartDate: string
        searchForm: {
            keyword: string
        }
        searchRailCollapsed: boolean
        activeSource: CalEvent['source'] | null
        highlightedSources: CalEvent['source'][]
        selectedCellDateKey: string | null
        selectedEventId: number | null
    }

    interface EventDetailForm {
        title: string
        date: string
        startTime: string
        endTime: string
        location: string
        description: string
        link: string
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

    const addMonths = (input: Date, months: number) => (
        new Date(input.getFullYear(), input.getMonth() + months, input.getDate())
    )

    const shiftVisibleMonth = (offset: number) => {
        const centerDate = addDays(viewStartDate.value, 21)
        const targetMonthStart = new Date(centerDate.getFullYear(), centerDate.getMonth() + offset, 1)
        viewStartDate.value = startOfWeek(targetMonthStart)
    }

    const today = new Date()
    const viewStartDate = ref(startOfWeek(new Date(today.getFullYear(), today.getMonth(), 1)))
    const todayKey = toDateKey(today)
    const calendarWorkspaceStyle = computed(() => ({
        '--calendar-selected-date-bg': theme.current.value.dark ? '#202a33' : '#eaf3ff',
        '--calendar-mini-header-color': theme.current.value.dark ? '#9a9a9a' : '#666666',
        '--calendar-mini-muted-color': theme.current.value.dark ? '#747474' : '#9a9a9a',
        '--calendar-source-action-color': theme.current.value.dark ? '#a8a8a8' : '#5f5f5f',
        '--calendar-text-color': theme.current.value.dark ? '#f2f2f2' : '#1f1f1f',
        '--calendar-muted-text-color': theme.current.value.dark ? '#b8b8b8' : '#5f5f5f',
        '--calendar-panel-bg': theme.current.value.dark ? '#121212' : '#ffffff',
    }))

    const events = ref<CalEvent[]>([])
    const sourceScopedEvents = ref<CalEvent[]>([])
    const searchResults = ref<CalEvent[]>([])
    const draftEvent = ref<CalEvent | null>(null)
    const selectedCell = ref<CalendarCell | null>(null)
    const selectedEventId = ref<number | null>(null)
    const eventDetailForm = reactive<EventDetailForm>({
        title: '',
        date: '',
        startTime: '',
        endTime: '',
        location: '',
        description: '',
        link: '',
    })
    const eventDetailSnapshot = ref('')
    const eventDetailSaving = ref(false)
    const eventDetailError = ref('')
    const activeSource = ref<CalEvent['source'] | null>(null)
    const sourceCatalog = ref<{ id: number; title: string; isVisible: boolean; colorHex: string }[]>([])

    const searchForm = reactive({
        keyword: '',
    })
    const searchLoading = ref(false)
    const searchError = ref('')
    const searchRailCollapsed = ref(false)

    const sourceColorDialogOpen = ref(false)
    const colorEditingSource = ref('')
    const colorEditingValue = ref('#4ca8df')
    const sourceColorSaving = ref(false)
    const eventColorMenuOpen = ref(false)
    const eventColorSaving = ref(false)
    const colorNotice = ref('')
    const colorNoticeOpen = ref(false)
    const persistenceReady = ref(false)
    const calendarPollTimer = ref<ReturnType<typeof window.setInterval> | null>(null)
    const calendarScrollRefreshTimer = ref<ReturnType<typeof window.setTimeout> | null>(null)
    const searchDebounceTimer = ref<ReturnType<typeof window.setTimeout> | null>(null)
    const calendarWheelScrolling = ref(false)
    let sourceEventsRequestToken = 0
    let visibleEventsRequestToken = 0
    let draftEventSequence = -1
    let calendarWheelDelta = 0
    let calendarWheelFrameId: number | null = null
    let lastCalendarWheelEventAt = 0

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

    }, { immediate: true })

    const sourceHighlighted = (source: CalEvent['source']) => highlightedSources.value.has(source)

    const calendarColorOptions = CALENDAR_COLOR_OPTIONS

    const sourceColorHex = (source: string) =>
        normalizeCalendarColor(sourceColorMap.value.get(source), '#4ca8df')

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
            sourceMeta.colorHex = normalizeCalendarColor(updated.color, sourceMeta.colorHex)
            highlightedSources.value = updated.is_visible
                ? new Set([...prev, source])
                : new Set(Array.from(prev).filter(item => item !== source))
        } catch (error) {
            highlightedSources.value = prev
            console.error(error)
            searchError.value = 'Update source visibility failed.'
        }
    }

    const setSourceColor = async (color: string) => {
        const source = colorEditingSource.value
        const nextHex = normalizeCalendarColor(color, colorEditingValue.value)
        if (!source) return

        const sourceMeta = sourceCatalog.value.find(item => item.title === source)
        if (!sourceMeta) {
            searchError.value = `Source ${source} is not managed by backend. Refresh source list first.`
            return
        }

        sourceColorSaving.value = true
        colorEditingValue.value = nextHex
        try {
            const updated = await updateCalendarSource(sourceMeta.id, { color: nextHex })
            sourceMeta.colorHex = normalizeCalendarColor(updated.color, nextHex)
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
    const expandedFetchStart = computed(() => (
        visibleStart.value ? toDateKey(addMonths(fromDateKey(visibleStart.value), -2)) : ''
    ))
    const expandedFetchEnd = computed(() => (
        visibleEnd.value ? toDateKey(addMonths(fromDateKey(visibleEnd.value), 2)) : ''
    ))
    const searchResultEvents = computed(() =>
        [...searchResults.value].sort((a, b) => {
            const dateCmp = a.date.localeCompare(b.date)
            return dateCmp !== 0 ? dateCmp : getEventStartTime(a).localeCompare(getEventStartTime(b))
        })
    )

    const buildSearchQuery = () => {
        const keyword = searchForm.keyword.trim()
        if (!keyword) return null

        return {
            key_word: keyword,
            start_time: ALL_EVENTS_START_TIME,
            end_time: ALL_EVENTS_END_TIME,
        }
    }

    const runSearch = async (silent = false): Promise<boolean> => {
        const query = buildSearchQuery()
        if (!query) {
            searchLoading.value = false
            searchError.value = ''
            searchResults.value = []
            return false
        }

        searchLoading.value = true
        if (!silent) searchError.value = ''
        try {
            searchResults.value = await searchCalendarEvents(query)
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

    const clearSearchDebounceTimer = () => {
        if (typeof window === 'undefined') return
        if (!searchDebounceTimer.value) return
        window.clearTimeout(searchDebounceTimer.value)
        searchDebounceTimer.value = null
    }

    const scheduleKeywordSearch = () => {
        clearSearchDebounceTimer()

        if (!searchForm.keyword.trim()) {
            searchLoading.value = false
            searchError.value = ''
            searchResults.value = []
            return
        }

        if (typeof window === 'undefined') {
            void runSearch(true)
            return
        }

        searchLoading.value = true
        searchDebounceTimer.value = window.setTimeout(() => {
            searchDebounceTimer.value = null
            void runSearch(true)
        }, 260)
    }

    const clearSearch = () => {
        clearSearchDebounceTimer()
        searchForm.keyword = ''
        searchError.value = ''
        searchLoading.value = false
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

            sourceScopedEvents.value = rows.filter(item => item.source === normalizedSource)
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
                colorHex: normalizeCalendarColor(row.color, '#4ca8df'),
            }))
        } catch (error) {
            console.error(error)
            sourceCatalog.value = []
        }
    }

    const loadVisibleEvents = async (silent = false) => {
        const requestToken = ++visibleEventsRequestToken
        const start = expandedFetchStart.value
        const end = expandedFetchEnd.value
        if (!silent) searchError.value = ''
        try {
            const rows = await getCalendarEvents({
                start,
                end,
            })
            if (requestToken !== visibleEventsRequestToken) return
            events.value = rows
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

    const cancelCalendarWheelFrame = () => {
        if (typeof window === 'undefined') return
        if (calendarWheelFrameId === null) return
        window.cancelAnimationFrame(calendarWheelFrameId)
        calendarWheelFrameId = null
    }

    const resetCalendarWheelState = () => {
        cancelCalendarWheelFrame()
        calendarWheelDelta = 0
        lastCalendarWheelEventAt = 0
    }

    const cancelCalendarScrollRefresh = () => {
        clearCalendarScrollRefreshTimer()
        resetCalendarWheelState()
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
            calendarWheelDelta = 0
            calendarWheelScrolling.value = false
            void loadVisibleEvents(silent)
        }, CALENDAR_SCROLL_REFRESH_DEBOUNCE_MS)
    }

    const normalizeWheelDelta = (event: WheelEvent) => {
        if (event.deltaMode === WheelEvent.DOM_DELTA_LINE) return event.deltaY * CALENDAR_WHEEL_LINE_DELTA
        if (event.deltaMode === WheelEvent.DOM_DELTA_PAGE) return event.deltaY * CALENDAR_WHEEL_PAGE_DELTA
        return event.deltaY
    }

    const scheduleCalendarWheelFrame = () => {
        if (typeof window === 'undefined') return
        if (calendarWheelFrameId !== null) return
        calendarWheelFrameId = window.requestAnimationFrame(applyCalendarWheelScroll)
    }

    function applyCalendarWheelScroll () {
        calendarWheelFrameId = null
        const absDelta = Math.abs(calendarWheelDelta)
        if (absDelta < CALENDAR_WHEEL_STEP_DELTA) return

        const direction = Math.sign(calendarWheelDelta)
        const rawSteps = Math.trunc(absDelta / CALENDAR_WHEEL_STEP_DELTA) * direction
        const steps = Math.max(-CALENDAR_MAX_WHEEL_STEPS_PER_FRAME, Math.min(CALENDAR_MAX_WHEEL_STEPS_PER_FRAME, rawSteps))

        calendarWheelDelta -= steps * CALENDAR_WHEEL_STEP_DELTA
        viewStartDate.value = addDays(viewStartDate.value, steps * 7)
        scheduleCalendarScrollRefresh(true)

        if (Math.abs(calendarWheelDelta) >= CALENDAR_WHEEL_STEP_DELTA) {
            scheduleCalendarWheelFrame()
        }
    }

    const pollCalendarData = async () => {
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
            await loadSources()
            await loadVisibleEvents(true)
            if (activeSource.value) {
                await loadSourceScopedEvents(activeSource.value, true)
            }
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
            void pollCalendarData()
        }, CALENDAR_POLL_INTERVAL_MS)

        pollingWindow.__calendarIndexPollTimer__ = calendarPollTimer.value
    }

    const allCalendarEvents = computed(() => (
        draftEvent.value ? [...events.value, draftEvent.value] : events.value
    ))

    const visibleRangeEvents = computed(() =>
        allCalendarEvents.value.filter(e => {
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

    const displayEvents = computed(() =>
        visibleRangeEvents.value.filter(e => sourceHighlighted(e.source))
    )

    const sortPanelEvents = (items: CalEvent[]) => (
        [...items].sort((a, b) => {
            const dateCmp = a.date.localeCompare(b.date)
            return dateCmp !== 0 ? dateCmp : getEventStartTime(a).localeCompare(getEventStartTime(b))
        })
    )

    const selectedDayEvents = computed(() => {
        if (!selectedCell.value) return []
        return sortPanelEvents(getEventsForDate(filteredEvents.value, selectedCell.value.dateKey))
    })

    const panelEvents = computed(() => selectedDayEvents.value)

    const isDraftEvent = (event: CalEvent | null | undefined) => !!event && event.id < 0
    const isManageableEvent = (event: CalEvent | null | undefined) => {
        return !!event && ['user', 'agent'].includes(`${event.source}`)
    }

    const selectedEventDetail = computed(() => {
        if (!selectedEventId.value) return null
        return (
            draftEvent.value?.id === selectedEventId.value ? draftEvent.value : null
        ) ?? (
                events.value.find(ev => ev.id === selectedEventId.value)
                ?? sourceScopedEvents.value.find(ev => ev.id === selectedEventId.value)
                ?? searchResults.value.find(ev => ev.id === selectedEventId.value)
                ?? null
            )
    })

    const selectedEventIsDraft = computed(() => isDraftEvent(selectedEventDetail.value))
    const selectedEventEditable = computed(() => isManageableEvent(selectedEventDetail.value))
    const selectedEventOwnColor = computed(() => normalizeOptionalCalendarColor(selectedEventDetail.value?.color))
    const selectedEventColor = computed(() => {
        const event = selectedEventDetail.value
        return selectedEventOwnColor.value ?? (event ? sourceColorHex(event.source) : '#4ca8df')
    })
    const selectedEventColorLabel = computed(() => (
        selectedEventOwnColor.value ? getCalendarColorLabel(selectedEventOwnColor.value) : 'Source'
    ))

    const normalizeTimeInputValue = (value: unknown) => `${value ?? ''}`

    const normalizeEventDetailTimeRange = () => {
        const { startTime, endTime } = eventDetailForm
        if (!startTime || !endTime || endTime >= startTime) return
        eventDetailForm.endTime = startTime
    }

    const updateEventStartTime = (value: unknown) => {
        eventDetailForm.startTime = normalizeTimeInputValue(value)
        normalizeEventDetailTimeRange()
        eventDetailError.value = ''
    }

    const updateEventEndTime = (value: unknown) => {
        const next = normalizeTimeInputValue(value)
        eventDetailForm.endTime = eventDetailForm.startTime && next && next < eventDetailForm.startTime
            ? eventDetailForm.startTime
            : next
        eventDetailError.value = ''
    }

    const eventDetailFormPayload = () => ({
        title: eventDetailForm.title.trim(),
        date: eventDetailForm.date,
        startTime: eventDetailForm.startTime || '00:00',
        endTime: eventDetailForm.endTime || eventDetailForm.startTime || '00:00',
        location: eventDetailForm.location.trim(),
        description: eventDetailForm.description.trim(),
        link: eventDetailForm.link.trim(),
    })

    const syncEventDetailForm = (event: CalEvent | null) => {
        eventDetailError.value = ''
        if (!event) {
            eventDetailSnapshot.value = ''
            Object.assign(eventDetailForm, {
                title: '',
                date: '',
                startTime: '',
                endTime: '',
                location: '',
                description: '',
                link: '',
            })
            return
        }

        Object.assign(eventDetailForm, {
            title: event.title,
            date: event.date,
            startTime: event.startTime || '12:00',
            endTime: event.endTime || event.startTime || '12:00',
            location: event.location ?? '',
            description: event.description ?? '',
            link: event.link ?? '',
        })
        normalizeEventDetailTimeRange()
        eventDetailSnapshot.value = JSON.stringify(eventDetailFormPayload())
    }

    const patchEventInList = (items: CalEvent[], eventId: number, patch: Partial<CalEvent>) => (
        items.map(item => item.id === eventId ? { ...item, ...patch } : item)
    )

    const setSelectedEventColor = async (color: string | null) => {
        const event = selectedEventDetail.value
        if (!event || !selectedEventEditable.value || eventColorSaving.value) return

        const nextHex = color ? normalizeCalendarColor(color, sourceColorHex(event.source)) : null
        eventColorMenuOpen.value = false
        if (normalizeOptionalCalendarColor(event.color) === nextHex) return

        if (isDraftEvent(event)) {
            draftEvent.value = { ...event, color: nextHex }
            return
        }

        const previousEvents = [...events.value]
        const previousSourceScopedEvents = [...sourceScopedEvents.value]
        const previousSearchResults = [...searchResults.value]
        const patch: Partial<CalEvent> = { color: nextHex }

        events.value = patchEventInList(events.value, event.id, patch)
        sourceScopedEvents.value = patchEventInList(sourceScopedEvents.value, event.id, patch)
        searchResults.value = patchEventInList(searchResults.value, event.id, patch)

        eventColorSaving.value = true
        eventDetailError.value = ''
        try {
            await updateCalendarEvent(event.id, patch)
            await refreshFromAllEventsOnce()
        } catch (error) {
            console.error(error)
            events.value = previousEvents
            sourceScopedEvents.value = previousSourceScopedEvents
            searchResults.value = previousSearchResults
            eventDetailError.value = 'Update event color failed.'
        } finally {
            eventColorSaving.value = false
        }
    }

    const saveSelectedEventDetail = async () => {
        const event = selectedEventDetail.value
        if (!event || !selectedEventEditable.value || eventDetailSaving.value) return

        const payload = eventDetailFormPayload()
        const nextSnapshot = JSON.stringify(payload)
        if (nextSnapshot === eventDetailSnapshot.value) return

        if (payload.endTime < payload.startTime) {
            eventDetailError.value = 'End time must be later than start time.'
            return
        }

        const patch: Partial<CalEvent> = {
            title: payload.title,
            date: payload.date,
            time: payload.startTime,
            startTime: payload.startTime,
            endTime: payload.endTime,
            location: payload.location,
            description: payload.description,
            link: payload.link,
            informType: event.informType,
        }

        if (isDraftEvent(event)) {
            draftEvent.value = { ...event, ...patch }
        }

        if (!payload.title || !payload.date) {
            if (isDraftEvent(event)) {
                eventDetailError.value = ''
                return
            }
            eventDetailError.value = 'Title and date are required.'
            return
        }

        eventDetailSaving.value = true
        eventDetailError.value = ''

        if (isDraftEvent(event)) {
            const previousDraftEvent = draftEvent.value
            const createPayload: Omit<CalEvent, 'id'> = {
                title: payload.title,
                source: 'user',
                color: normalizeOptionalCalendarColor(event.color),
                date: payload.date,
                time: payload.startTime,
                startTime: payload.startTime,
                endTime: payload.endTime,
                location: payload.location,
                description: payload.description,
                link: payload.link,
                informType: event.informType ?? 'none',
            }

            try {
                const created = await createCalendarEvent(createPayload)
                draftEvent.value = null
                events.value = [...events.value, created]
                if (activeSource.value === created.source) {
                    sourceScopedEvents.value = [...sourceScopedEvents.value, created]
                }
                selectedEventId.value = created.id
                eventDetailSnapshot.value = nextSnapshot
                await refreshCalendarData()
            } catch (error) {
                console.error(error)
                draftEvent.value = previousDraftEvent
                eventDetailError.value = 'Save failed. Please check backend response.'
                syncEventDetailForm(selectedEventDetail.value)
            } finally {
                eventDetailSaving.value = false
            }
            return
        }

        const previousEvents = [...events.value]
        const previousSourceScopedEvents = [...sourceScopedEvents.value]
        const previousSearchResults = [...searchResults.value]

        events.value = patchEventInList(events.value, event.id, patch)
        sourceScopedEvents.value = patchEventInList(sourceScopedEvents.value, event.id, patch)
        searchResults.value = patchEventInList(searchResults.value, event.id, patch)

        try {
            await updateCalendarEvent(event.id, patch)
            eventDetailSnapshot.value = nextSnapshot
            await refreshFromAllEventsOnce()
        } catch (error) {
            console.error(error)
            events.value = previousEvents
            sourceScopedEvents.value = previousSourceScopedEvents
            searchResults.value = previousSearchResults
            eventDetailError.value = 'Save failed. Please check backend response.'
            syncEventDetailForm(selectedEventDetail.value)
        } finally {
            eventDetailSaving.value = false
        }
    }

    watch(selectedEventDetail, (event) => {
        syncEventDetailForm(event)
    }, { immediate: true })

    const discardEmptyDraftEvent = () => {
        const draft = draftEvent.value
        if (!draft) return
        if (eventDetailForm.title.trim()) return

        draftEvent.value = null
        eventDetailSnapshot.value = ''
        eventDetailError.value = ''
        if (selectedEventId.value === draft.id) selectedEventId.value = null
    }

    const closeSelectedEventDetail = () => {
        discardEmptyDraftEvent()
        selectedEventId.value = null
    }

    const focusDateKey = async (dateKey: string) => {
        const inCurrentView = cells.value.some(c => c.dateKey === dateKey)
        if (!inCurrentView) {
            cancelCalendarScrollRefresh()
            const targetDate = fromDateKey(dateKey)
            viewStartDate.value = startOfWeek(new Date(targetDate.getFullYear(), targetDate.getMonth(), 1))
            await nextTick()
        }

        const cell = cells.value.find(c => c.dateKey === dateKey)
        if (cell) selectedCell.value = cell
    }

    const getEventSpanDays = (event: CalEvent) => {
        if (!event.endDate) return 0
        const startTime = fromDateKey(event.date).getTime()
        const endTime = fromDateKey(event.endDate).getTime()
        return Math.max(0, Math.round((endTime - startTime) / 86400000))
    }

    const moveEventToDate = async (payload: { event: CalEvent; dateKey: string }) => {
        const { event, dateKey } = payload
        if (event.source !== 'user' || isDraftEvent(event) || event.date === dateKey) return

        const previousEvents = [...events.value]
        const previousSourceScopedEvents = [...sourceScopedEvents.value]
        const previousSearchResults = [...searchResults.value]
        const spanDays = getEventSpanDays(event)
        const patch: Partial<CalEvent> = {
            date: dateKey,
            endDate: spanDays > 0 ? toDateKey(addDays(fromDateKey(dateKey), spanDays)) : undefined,
            time: event.startTime || event.time || '00:00',
            startTime: event.startTime || event.time || '00:00',
            endTime: event.endTime || event.startTime || event.time || '00:00',
        }

        events.value = patchEventInList(events.value, event.id, patch)
        sourceScopedEvents.value = patchEventInList(sourceScopedEvents.value, event.id, patch)
        searchResults.value = patchEventInList(searchResults.value, event.id, patch)
        selectedEventId.value = event.id
        searchError.value = ''
        await focusDateKey(dateKey)

        try {
            await updateCalendarEvent(event.id, patch)
            await refreshFromAllEventsOnce()
        } catch (error) {
            console.error(error)
            events.value = previousEvents
            sourceScopedEvents.value = previousSourceScopedEvents
            searchResults.value = previousSearchResults
            searchError.value = 'Move failed. Please check backend response.'
            await focusDateKey(event.date)
        }
    }

    const makeDraftEvent = (dateKey: string): CalEvent => ({
        id: draftEventSequence--,
        title: '',
        source: 'user',
        color: null,
        time: '12:00',
        startTime: '12:00',
        endTime: '12:00',
        date: dateKey,
        location: '',
        description: '',
        link: '',
        informType: 'none',
    })

    const startInlineCreate = async () => {
        discardEmptyDraftEvent()

        const targetDate = selectedCell.value?.dateKey ?? todayKey
        const nextDraft = makeDraftEvent(targetDate)
        draftEvent.value = nextDraft
        selectedEventId.value = nextDraft.id
        searchRailCollapsed.value = false
        await focusDateKey(targetDate)
    }

    const prevMonth = () => {
        cancelCalendarScrollRefresh()
        shiftVisibleMonth(-1)
    }

    const nextMonth = () => {
        cancelCalendarScrollRefresh()
        shiftVisibleMonth(1)
    }

    const goToday = async () => {
        await focusDateKey(todayKey)
    }

    const onCellClick = (cell: CalendarCell) => {
        discardEmptyDraftEvent()
        selectedCell.value = cell
        selectedEventId.value = null
    }

    const onEventClick = async (ev: CalEvent) => {
        selectedEventId.value = ev.id
        searchRailCollapsed.value = false
        await focusDateKey(ev.date)
    }

    const onCalendarWheel = (event: WheelEvent) => {
        const normalizedDelta = normalizeWheelDelta(event)
        if (Math.abs(normalizedDelta) < 1) return

        const now = Date.now()
        if (now - lastCalendarWheelEventAt > CALENDAR_WHEEL_ACCUMULATOR_RESET_MS) {
            calendarWheelDelta = 0
        }
        lastCalendarWheelEventAt = now

        calendarWheelDelta += normalizedDelta
        scheduleCalendarWheelFrame()
    }

    const sourceChipStyle = (source: CalEvent['source']) => {
        const color = sourceColorHex(source)
        const selected = activeSource.value === source
        return sourceHighlighted(source)
            ? {
                '--strip-accent': color,
                background: 'transparent',
                color: 'var(--calendar-text-color)',
                borderColor: selected ? color : 'rgba(var(--v-border-color), 0.24)',
                boxShadow: selected ? `inset 0 0 0 1px ${color}` : 'none'
            }
            : {
                '--strip-accent': color,
                background: 'transparent',
                color: 'var(--calendar-muted-text-color)',
                borderColor: selected ? color : 'rgba(var(--v-border-color), 0.18)',
                boxShadow: selected ? `inset 0 0 0 1px ${color}` : 'none'
            }
    }

    const persistCalendarPageState = () => {
        if (typeof window === 'undefined') return

        const payload: CalendarPagePersistedState = {
            viewStartDate: toDateKey(viewStartDate.value),
            searchForm: {
                keyword: searchForm.keyword,
            },
            searchRailCollapsed: searchRailCollapsed.value,
            activeSource: activeSource.value,
            highlightedSources: Array.from(highlightedSources.value),
            selectedCellDateKey: selectedCell.value?.dateKey ?? null,
            selectedEventId: selectedEventIsDraft.value ? null : selectedEventId.value,
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
            }

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

    const openEventContextMenu = async (payload: { event: CalEvent; mouseEvent: MouseEvent }) => {
        await onEventClick(payload.event)
    }

    const refreshCalendarData = async () => {
        await loadVisibleEvents(true)
        if (activeSource.value) {
            await loadSourceScopedEvents(activeSource.value, true)
        }
    }

    const refreshFromAllEventsOnce = async () => {
        const allEvents = await searchCalendarEvents({
            start_time: ALL_EVENTS_START_TIME,
            end_time: ALL_EVENTS_END_TIME,
        })

        const start = expandedFetchStart.value
        const end = expandedFetchEnd.value
        events.value = allEvents.filter(event => {
            const eventEnd = event.endDate ?? event.date
            return eventEnd >= start && event.date <= end
        })

        if (activeSource.value) {
            sourceScopedEvents.value = allEvents.filter(event => event.source === activeSource.value)
        }
    }

    const deleteEvent = async (ev: CalEvent) => {
        if (!isManageableEvent(ev)) return

        if (isDraftEvent(ev)) {
            draftEvent.value = null
            if (selectedEventId.value === ev.id) selectedEventId.value = null
            return
        }

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
            searchRailCollapsed,
            () => searchForm.keyword,
        ],
        () => {
            if (!persistenceReady.value) return
            persistCalendarPageState()
        },
        { deep: true }
    )

    watch(() => searchForm.keyword, scheduleKeywordSearch)

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
        clearSearchDebounceTimer()
        stopCalendarPolling()
    })
</script>

<style scoped>
    .calendar-workspace {
        --calendar-content-radius: 8px;
        --calendar-selected-date-bg: #eaf3ff;
        --calendar-mini-header-color: #666666;
        --calendar-mini-muted-color: #8f8f8f;
        --calendar-source-action-color: #5f5f5f;
        --calendar-text-color: #1f1f1f;
        --calendar-muted-text-color: #5f5f5f;
        --calendar-panel-bg: #ffffff;

        background: rgb(var(--v-theme-surface));
        color: var(--calendar-text-color);
    }

    .calendar-center-panel {
        background: var(--calendar-panel-bg);
        border-top-left-radius: var(--calendar-content-radius);
        border-top-right-radius: var(--calendar-content-radius);
        border-bottom-left-radius: var(--calendar-content-radius);
        overflow: hidden;
    }

    .calendar-toolbar,
    .calendar-grid-shell {
        background: transparent;
    }

    .calendar-right-panel {
        width: 280px;
        min-width: 280px;
        overflow-y: auto;
        background: rgb(var(--v-theme-surface));
    }

    .calendar-toolbar-actions :deep(.v-btn__overlay) {
        display: none !important;
    }

    .calendar-toolbar-actions {
        background: transparent !important;
    }

    .source-chip {
        width: 100%;
        min-height: 30px;
        justify-content: flex-start;
        position: relative;
        font-weight: 500;
        border-radius: 8px;
        border: 1px solid rgba(var(--v-border-color), 0.18) !important;
        padding-left: 8px;
    }

    .source-chip :deep(.v-chip__content) {
        width: 100%;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .calendar-section-label {
        background: transparent;
        color: var(--calendar-muted-text-color);
        font-size: 0.75rem;
        line-height: 1rem;
    }

    .calendar-helper-text {
        background: transparent;
        color: var(--calendar-muted-text-color);
        font-size: 0.75rem;
        line-height: 1rem;
    }

    .source-action-btn {
        width: 22px !important;
        height: 22px !important;
        min-width: 22px !important;
        color: var(--calendar-source-action-color) !important;
        background: transparent !important;
    }

    .source-action-btn :deep(.v-btn__overlay),
    .source-action-btn :deep(.v-btn__underlay) {
        display: none !important;
    }

    .source-action-btn :deep(.v-icon) {
        color: var(--calendar-source-action-color) !important;
    }

    .search-result-list {
        max-height: 320px;
        overflow-y: auto;
        padding-block: 2px;
        background: transparent;
    }

    .calendar-search-count {
        background: transparent;
        color: var(--calendar-muted-text-color);
        font-size: 0.75rem;
        line-height: 1rem;
    }

    .calendar-search-item {
        min-height: 38px;
    }

    .calendar-search-item-strip {
        align-self: stretch;
        min-height: 26px;
        margin-block: 5px;
    }

    .calendar-search-item-title {
        font-size: 0.75rem;
        font-weight: 600;
        line-height: 1rem;
    }

    .calendar-search-item-subtitle {
        color: var(--calendar-muted-text-color);
        font-size: 0.6875rem;
        line-height: 0.875rem;
    }

    .calendar-event-detail-body {
        display: flex;
        flex-direction: column;
        gap: 14px;
        padding: 12px;
        background: transparent;
    }

    .calendar-detail-title {
        margin-top: -4px;
    }

    .calendar-detail-title :deep(.v-field__input) {
        min-height: 34px;
        padding: 0;
        font-size: 20px;
        font-weight: 700;
        line-height: 1.25;
    }

    .calendar-detail-draft-hint {
        margin-top: -10px;
        background: transparent;
        color: var(--calendar-muted-text-color);
        font-size: 11px;
    }

    .calendar-detail-property {
        display: grid;
        grid-template-columns: 14px minmax(0, 1fr);
        align-items: center;
        column-gap: 6px;
        row-gap: 5px;
        min-width: 0;
        background: transparent;
    }

    .calendar-detail-property-icon {
        grid-column: 1;
        grid-row: 1;
        align-self: center;
        margin-top: 0 !important;
        color: var(--calendar-muted-text-color);
    }

    .calendar-detail-property-content {
        display: contents;
        min-width: 0;
        background: transparent;
    }

    .calendar-detail-label {
        display: block;
        grid-column: 2;
        margin-bottom: 0;
        color: var(--calendar-muted-text-color);
        font-size: 11px;
        line-height: 1;
    }

    .calendar-detail-property-content> :not(.calendar-detail-label) {
        grid-column: 1 / -1;
        width: 100%;
    }

    .calendar-detail-field,
    .calendar-detail-field :deep(.v-input__control) {
        background: transparent !important;
        background-color: transparent !important;
        box-shadow: none !important;
    }

    .calendar-detail-field :deep(.v-field) {
        border: 1px solid transparent;
        background: transparent !important;
        background-color: transparent !important;
        box-shadow: none !important;
        transition: border-color 0.16s ease;
    }

    .calendar-detail-field :deep(.v-field__outline) {
        display: none;
    }

    .calendar-detail-field :deep(.v-field__field),
    .calendar-detail-field :deep(input),
    .calendar-detail-field :deep(textarea) {
        background: transparent !important;
        background-color: transparent !important;
    }

    .calendar-detail-field :deep(.v-field--active),
    .calendar-detail-field :deep(.v-field--focused),
    .calendar-detail-field :deep(.v-field--active .v-field__field),
    .calendar-detail-field :deep(.v-field--focused .v-field__field),
    .calendar-detail-field :deep(.v-field--active .v-field__input),
    .calendar-detail-field :deep(.v-field--focused .v-field__input) {
        background: transparent !important;
        background-color: transparent !important;
    }

    .calendar-detail-field :deep(.v-field__field) {
        flex: 1 1 auto;
        min-width: 0;
        width: 100%;
    }

    .calendar-detail-field :deep(.v-field__overlay) {
        display: none !important;
    }

    .calendar-detail-field {
        min-width: 0;
        width: 100%;
    }

    .calendar-detail-field :deep(.v-field:hover) {
        border-color: rgb(var(--v-border-color));
        background: transparent !important;
    }

    .calendar-detail-field :deep(.v-field--focused) {
        border-color: var(--calendar-text-color);
        background: transparent !important;
    }

    .calendar-detail-field :deep(.v-field__input) {
        box-sizing: border-box;
        flex: 1 1 auto;
        min-height: 32px;
        min-width: 0;
        max-width: none;
        width: 100%;
        padding-top: 0;
        padding-bottom: 0;
        font-size: 13px;
        background: transparent !important;
        background-color: transparent !important;
    }

    .calendar-detail-field :deep(input[type="date"].v-field__input),
    .calendar-detail-field :deep(input[type="time"].v-field__input) {
        appearance: none;
        -webkit-appearance: none;
        display: block;
        position: relative;
        padding-right: 32px;
    }

    .calendar-detail-field :deep(input[type="date"]::-webkit-calendar-picker-indicator),
    .calendar-detail-field :deep(input[type="time"]::-webkit-calendar-picker-indicator) {
        position: absolute;
        top: 50%;
        right: 8px;
        width: 18px;
        height: 18px;
        margin: 0;
        transform: translateY(-50%);
        cursor: pointer;
    }

    .calendar-detail-field :deep(textarea.v-field__input) {
        padding-top: 8px;
        padding-bottom: 8px;
        line-height: 1.45;
    }

    .calendar-detail-time-separator {
        color: var(--calendar-muted-text-color);
        font-size: 11px;
        line-height: 32px;
    }

    .calendar-detail-read-title {
        overflow-wrap: anywhere;
        background: transparent;
        font-size: 20px;
        font-weight: 700;
        line-height: 1.25;
    }

    .calendar-detail-value {
        font-size: 13px;
        font-weight: 600;
        overflow-wrap: anywhere;
    }

    .calendar-detail-meta-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        min-height: 24px;
        background: transparent;
        color: var(--calendar-muted-text-color);
        font-size: 12px;
    }

    .calendar-detail-meta-row strong {
        font-weight: 600;
    }

    .calendar-color-value-btn {
        min-width: 0;
        padding: 0 6px;
        color: var(--calendar-text-color);
    }

    .calendar-color-value-btn :deep(.v-btn__content) {
        gap: 6px;
    }

    .calendar-color-list-item {
        min-height: 30px;
    }

    .calendar-color-menu {
        background: rgb(var(--v-theme-surface));
    }

    .event-detail-link {
        color: rgb(var(--v-theme-primary));
        text-decoration: none;
        word-break: break-all;
        font-size: 13px;
        font-weight: 600;
    }

    .event-detail-link:hover {
        text-decoration: underline;
    }

    .mini-weekday {
        color: var(--calendar-mini-header-color);
        font-size: 10px;
        line-height: 14px;
        text-align: center;
    }

    .mini-day-btn {
        border: 1px solid rgba(var(--v-border-color), 0.26);
        border-radius: 6px;
        background: transparent;
        color: var(--calendar-text-color);
        font-size: 10px;
        height: 24px;
        cursor: pointer;
    }

    .mini-day-btn.muted {
        background: transparent;
        color: var(--calendar-mini-muted-color);
        border-color: transparent;
    }

    .mini-day-btn.today {
        border-color: rgba(var(--v-theme-primary), 0.7);
    }

    .mini-day-btn.active {
        background: var(--calendar-selected-date-bg);
        border-color: rgba(var(--v-theme-primary), 0.72);
        color: var(--calendar-text-color);
    }
</style>
