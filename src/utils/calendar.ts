import type { CalEvent, CalendarCell, CalendarInformType } from '@/types/calendar'

// ─── Date Helpers ──────────────────────────────────────────────────────────────
export const toDateKey = (d: Date): string => {
    const y = d.getFullYear()
    const m = `${d.getMonth() + 1}`.padStart(2, '0')
    const day = `${d.getDate()}`.padStart(2, '0')
    return `${y}-${m}-${day}`
}

export const fromDateKey = (dateKey: string): Date => {
    const [y = '1970', m = '01', d = '01'] = dateKey.split('-')
    return new Date(
        Number.parseInt(y, 10) || 1970,
        (Number.parseInt(m, 10) || 1) - 1,
        Number.parseInt(d, 10) || 1,
    )
}

export const parseHHMM = (value?: string): { hour: number; minute: number } => {
    if (!value) return { hour: 0, minute: 0 }
    const [h = '0', m = '0'] = value.split(':')
    const hour = Math.min(23, Math.max(0, Number.parseInt(h, 10) || 0))
    const minute = Math.min(59, Math.max(0, Number.parseInt(m, 10) || 0))
    return { hour, minute }
}

export const toUnixSecondsByDateKey = (dateKey: string, hhmm = '00:00'): number => {
    const date = fromDateKey(dateKey)
    const { hour, minute } = parseHHMM(hhmm)
    date.setHours(hour, minute, 0, 0)
    return Math.floor(date.getTime() / 1000)
}

export const isSameDay = (a: Date, b: Date): boolean => toDateKey(a) === toDateKey(b)

/** Returns the Monday-start week index of a date within its month grid */
export const startOfMonth = (year: number, month: number): Date =>
    new Date(year, month, 1)

export const getDaysInMonth = (year: number, month: number): number =>
    new Date(year, month + 1, 0).getDate()

/** Returns the day-of-week offset so the grid starts on Sunday */
export const firstDayOfWeekOffset = (year: number, month: number): number =>
    new Date(year, month, 1).getDay()

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

/** Get all events for a specific date key */
export const getEventsForDate = (events: CalEvent[], dateKey: string): CalEvent[] =>
    events.filter(e => e.date === dateKey || (e.endDate && dateKey >= e.date && dateKey <= e.endDate))

/** Sort events by time ascending */
export const sortEvents = (events: CalEvent[]): CalEvent[] =>
    [...events].sort((a, b) => getEventStartTime(a).localeCompare(getEventStartTime(b)))

export const getEventStartTime = (event: CalEvent): string => event.startTime ?? event.time ?? ''

export const getEventEndTime = (event: CalEvent): string => event.endTime ?? ''

export const formatCompact12HourTime = (value?: string): string => {
    if (!value) return ''
    const start = value.split(' - ')[0]?.trim() ?? ''
    if (!start) return ''
    const { hour, minute } = parseHHMM(start)
    const meridiem = hour < 12 ? 'AM' : 'PM'
    const hour12 = hour % 12 || 12

    if (minute === 0) return `${hour12}${meridiem}`
    return `${hour12}:${`${minute}`.padStart(2, '0')}${meridiem}`
}

export const getEventChipTimeLabel = (event: CalEvent): string =>
    formatCompact12HourTime(getEventStartTime(event))

export const getEventDisplayTime = (event: CalEvent): string => {
    const start = getEventStartTime(event)
    const end = getEventEndTime(event)
    if (start && end) return `${start} - ${end}`
    return start
}

/** Generate a new unique id */
export const nextId = (items: { id: number }[]): number =>
    items.length > 0 ? Math.max(...items.map(i => i.id)) + 1 : 1

