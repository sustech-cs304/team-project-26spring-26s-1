export type CalendarInformType = 'none' | '10_minutes_before' | '5_minutes_before' | '1_hour_before' | '30_minutes_before' | 'at_start'

export interface CalEvent {
    id: number
    title: string
    source: string
    sourceId?: number
    sourceVisible?: boolean
    isVisible?: boolean
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

export interface CalendarCell {
    day: any
    date: Date
    /** YYYY-MM-DD */
    dateKey: string
    currentMonth: boolean
    isToday: boolean
}

export interface CalendarSourceItem {
    id: number
    title: string
    is_visible: boolean
    color: string
}

export interface CalendarSourceUpdate {
    is_visible?: boolean
    color?: string
}

export interface CalendarEventQuery {
    id?: number
    start_time?: number
    end_time?: number
    source?: string
    key_word?: string
}

export interface CalendarEventListResponse {
    message: string
    data: CalendarEventApiItem[]
}

export interface CalendarMessageResponse {
    message: string
}

export interface CalendarCreateResponse {
    message: string
    ids: number[]
}

export interface CalendarEventCreateItem {
    title: string
    description?: string
    location?: string
    link?: string
    start_time: number
    end_time: number
    inform_type: CalendarInformType
    color: string
}

export interface CalendarEventModifyItem extends Partial<CalendarEventCreateItem> {
    id: number
}

export interface CalendarEventApiItem {
    id: number
    title: string
    start_time: number
    end_time: number
    source: string | CalendarSourceItem
    color: string
    location: string
    link: string
    description: string
    inform_type: CalendarInformType
}

