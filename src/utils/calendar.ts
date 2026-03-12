// ─── Calendar Types ────────────────────────────────────────────────────────────
export type EventType = 'exam' | 'class' | 'personal' | 'deadline' | 'meeting'

export interface CalEvent {
    id: number
    title: string
    type: EventType
    /** HH:MM or HH:MM - HH:MM */
    time: string
    /** YYYY-MM-DD */
    date: string
    /** YYYY-MM-DD – only set when event spans multiple days (end date) */
    endDate?: string
    location?: string
    courseId?: string
    description?: string
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
            day: undefined
        })
    }

    // Current month
    for (let d = 1; d <= totalDays; d++) {
        const date = new Date(year, month, d)
        const dateKey = toDateKey(date)
        cells.push({
            date, dateKey, currentMonth: true, isToday: dateKey === todayKey,
            day: undefined
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
            day: undefined
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

export const eventTypeColor = (type: EventType) => EVENT_TYPE_COLOR[type] ?? 'primary'
export const eventTypeIcon = (type: EventType) => EVENT_TYPE_ICON[type] ?? 'mdi-calendar'

/** Get all events for a specific date key */
export const getEventsForDate = (events: CalEvent[], dateKey: string): CalEvent[] =>
    events.filter(e => e.date === dateKey || (e.endDate && dateKey >= e.date && dateKey <= e.endDate))

/** Sort events by time ascending */
export const sortEvents = (events: CalEvent[]): CalEvent[] =>
    [...events].sort((a, b) => a.time.localeCompare(b.time))

/** Generate a new unique id */
export const nextId = (items: { id: number }[]): number =>
    items.length > 0 ? Math.max(...items.map(i => i.id)) + 1 : 1

