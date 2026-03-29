// ─── Calendar Types ────────────────────────────────────────────────────────────
export type EventType = 'exam' | 'class' | 'personal' | 'deadline' | 'meeting'
export type EventSource = string
export type CalendarColorName = 'red' | 'orange' | 'yellow' | 'green' | 'blue' | 'purple' | 'pink' | 'gray'
export type CalendarInformType = 'none' | '10_minutes_before' | '5_minutes_before' | '1_hour_before' | '30_minutes_before' | 'at_start'

export interface CalEvent {
    id: number
    title: string
    type: EventType
    source: EventSource
    sourceId?: number
    sourceVisible?: boolean
    /** Backend field mirror */
    informType?: CalendarInformType
    /** Backend field mirror */
    color?: string
    /** HH:MM or HH:MM - HH:MM */
    time: string
    /** HH:MM */
    startTime?: string
    /** HH:MM */
    endTime?: string
    /** YYYY-MM-DD */
    date: string
    /** YYYY-MM-DD – only set when event spans multiple days (end date) */
    endDate?: string
    location?: string
    courseId?: string
    description?: string
    link?: string
    allDay?: boolean
}

// ─── Date Helpers ──────────────────────────────────────────────────────────────
export const toDateKey = (d: Date): string => d.toISOString().slice(0, 10)

export const isSameDay = (a: Date, b: Date): boolean => toDateKey(a) === toDateKey(b)

/** Returns the Monday-start week index of a date within its month grid */
export const startOfMonth = (year: number, month: number): Date =>
    new Date(year, month, 1)

export const getDaysInMonth = (year: number, month: number): number =>
    new Date(year, month + 1, 0).getDate()

/** Returns the day-of-week offset so the grid starts on Sunday */
export const firstDayOfWeekOffset = (year: number, month: number): number =>
    new Date(year, month, 1).getDay()

export const EVENT_SOURCES: { value: EventSource; label: string }[] = [
    { value: 'course', label: 'Course' },
    { value: 'work', label: 'Work' },
    { value: 'life', label: 'Life' },
    { value: 'club', label: 'Club' },
    { value: 'family', label: 'Family' },
]

export const CALENDAR_COLOR_HEX: Record<CalendarColorName, string> = {
    red: '#ef4444',
    orange: '#f97316',
    yellow: '#eab308',
    green: '#22c55e',
    blue: '#3b82f6',
    purple: '#8b5cf6',
    pink: '#ec4899',
    gray: '#6b7280',
}

export const CALENDAR_INFORM_OPTIONS: { value: CalendarInformType; label: string }[] = [
    { value: 'none', label: 'None' },
    { value: '10_minutes_before', label: '10 minutes before' },
    { value: '5_minutes_before', label: '5 minutes before' },
    { value: '30_minutes_before', label: '30 minutes before' },
    { value: '1_hour_before', label: '1 hour before' },
    { value: 'at_start', label: 'At start' },
]

/**
 * Build the full 6-row (42-cell) calendar grid for a given month.
 * Cells outside the month are marked with `isCurrentMonth = false`.
 */
export function buildMonthGrid (year: number, month: number): CalendarCell[] {
    const cells: CalendarCell[] = []
    const offset = firstDayOfWeekOffset(year, month)
    const totalDays = getDaysInMonth(year, month)

    const todayKey = toDateKey(new Date())
    // Prev-month fill
    const prevTotalDays = getDaysInMonth(year, month - 1 < 0 ? 11 : month - 1)
    const prevMonth = month - 1 < 0 ? 11 : month - 1
    const prevYear = month - 1 < 0 ? year - 1 : year
    for (let i = offset - 1; i >= 0; i--) {
        const d = new Date(prevYear, prevMonth, prevTotalDays - i)
        const dateKey = toDateKey(d)
        cells.push({
            date: d, dateKey, currentMonth: false, isToday: dateKey === todayKey,
            day: d.getDate()
        })
    }

    // Current month
    for (let d = 1; d <= totalDays; d++) {
        const date = new Date(year, month, d)
        const dateKey = toDateKey(date)
        cells.push({
            date, dateKey, currentMonth: true, isToday: dateKey === todayKey,
            day: d
        })
    }

    // Next-month fill
    const nextMonth = month + 1 > 11 ? 0 : month + 1
    const nextYear = month + 1 > 11 ? year + 1 : year
    let nextDay = 1
    while (cells.length < 42) {
        const date = new Date(nextYear, nextMonth, nextDay++)
        const dateKey = toDateKey(date)
        cells.push({
            date, dateKey, currentMonth: false, isToday: dateKey === todayKey,
            day: date.getDate()
        })
    }

    return cells
}

export interface CalendarCell {
    day: any
    date: Date
    /** YYYY-MM-DD */
    dateKey: string
    currentMonth: boolean
    isToday: boolean
}

// ─── Event Helpers ─────────────────────────────────────────────────────────────
export const EVENT_TYPE_COLOR: Record<EventType, string> = {
    exam: 'error',
    class: 'primary',
    personal: 'info',
    deadline: 'warning',
    meeting: 'secondary',
}

export const EVENT_TYPE_ICON: Record<EventType, string> = {
    exam: 'mdi-book-open-outline',
    class: 'mdi-school-outline',
    personal: 'mdi-account-outline',
    deadline: 'mdi-clock-alert-outline',
    meeting: 'mdi-account-group-outline',
}

export const EVENT_TYPE_RAW_COLOR: Record<EventType, string> = {
    exam: 'var(--v-theme-error)',
    class: 'var(--v-theme-primary)',
    personal: 'var(--v-theme-info)',
    deadline: 'var(--v-theme-warning)',
    meeting: 'var(--v-theme-secondary)',
}

export const EVENT_SOURCE_RAW_COLOR: Record<string, string> = {
    course: '#2563eb',
    work: '#475569',
    life: '#059669',
    club: '#9333ea',
    family: '#ea580c',
}

export const eventTypeColor = (type: EventType) => EVENT_TYPE_COLOR[type] ?? 'primary'
export const eventTypeIcon = (type: EventType) => EVENT_TYPE_ICON[type] ?? 'mdi-calendar'
export const eventSourceRawColor = (source: EventSource) => EVENT_SOURCE_RAW_COLOR[source] ?? '#2563eb'
export const colorNameToHex = (name: CalendarColorName) => CALENDAR_COLOR_HEX[name]
export const colorHexToName = (hex?: string): CalendarColorName | null => {
    if (!hex) return null
    const normalized = hex.trim().toLowerCase()
    const entry = Object.entries(CALENDAR_COLOR_HEX).find(([, v]) => v.toLowerCase() === normalized)
    return entry ? entry[0] as CalendarColorName : null
}

/** Get all events for a specific date key */
export const getEventsForDate = (events: CalEvent[], dateKey: string): CalEvent[] =>
    events.filter(e => e.date === dateKey || (e.endDate && dateKey >= e.date && dateKey <= e.endDate))

/** Sort events by time ascending */
export const sortEvents = (events: CalEvent[]): CalEvent[] =>
    [...events].sort((a, b) => getEventStartTime(a).localeCompare(getEventStartTime(b)))

export const getEventStartTime = (event: CalEvent): string => event.startTime ?? event.time ?? ''

export const getEventEndTime = (event: CalEvent): string => event.endTime ?? ''

export const getEventDisplayTime = (event: CalEvent): string => {
    const start = getEventStartTime(event)
    const end = getEventEndTime(event)
    if (start && end) return `${start} - ${end}`
    return start
}

/** Generate a new unique id */
export const nextId = (items: { id: number }[]): number =>
    items.length > 0 ? Math.max(...items.map(i => i.id)) + 1 : 1

