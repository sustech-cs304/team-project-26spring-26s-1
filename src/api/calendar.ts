import http from '@/utils/http'
import type { CalEvent, CalendarColorName, CalendarInformType } from '@/utils/calendar'
import { colorHexToName, colorNameToHex, eventSourceRawColor, toDateKey } from '@/utils/calendar'

export interface CalendarSourceItem {
    id: number
    title: string
    is_visible: boolean
    color: CalendarColorName
}

export interface CalendarEventQuery {
    id?: number
    start_time?: number
    end_time?: number
    source?: string
    key_word?: string
}

interface CalendarEventListResponse {
    message: string
    data: CalendarEventApiItem[]
}

interface CalendarMessageResponse {
    message: string
}

interface CalendarCreateResponse {
    message: string
    ids: number[]
}

interface CalendarEventCreateItem {
    title: string
    description?: string
    location?: string
    link?: string
    start_time: number
    end_time: number
    inform_type: CalendarInformType
    color: CalendarColorName
}

interface CalendarEventModifyItem extends Partial<CalendarEventCreateItem> {
    id: number
}

interface CalendarEventApiItem {
    id: number
    title: string
    start_time: number
    end_time: number
    source: string | CalendarSourceItem
    color: CalendarColorName
    location: string
    link: string
    description: string
    inform_type: CalendarInformType
}

const parseHHMM = (value?: string): { hour: number; minute: number } => {
    if (!value) return { hour: 0, minute: 0 }
    const [h = '0', m = '0'] = value.split(':')
    const hour = Math.min(23, Math.max(0, Number.parseInt(h, 10) || 0))
    const minute = Math.min(59, Math.max(0, Number.parseInt(m, 10) || 0))
    return { hour, minute }
}

const toUnixSeconds = (dateKey: string, hhmm?: string): number => {
    const [y = '1970', mo = '01', d = '01'] = dateKey.split('-')
    const { hour, minute } = parseHHMM(hhmm)
    const date = new Date(
        Number.parseInt(y, 10) || 1970,
        (Number.parseInt(mo, 10) || 1) - 1,
        Number.parseInt(d, 10) || 1,
        hour,
        minute,
        0,
        0,
    )
    return Math.floor(date.getTime() / 1000)
}

const fromUnixSeconds = (value: number): Date => new Date(value * 1000)

const toHHMM = (date: Date): string => {
    const hh = `${date.getHours()}`.padStart(2, '0')
    const mm = `${date.getMinutes()}`.padStart(2, '0')
    return `${hh}:${mm}`
}

const toApiColor = (event: Pick<CalEvent, 'color' | 'source'>): CalendarColorName => {
    const named = colorHexToName(event.color)
    if (named) return named
    const sourceNamed = colorHexToName(eventSourceRawColor(event.source))
    return sourceNamed ?? 'blue'
}

const toCreatePayload = (event: Omit<CalEvent, 'id'>): CalendarEventCreateItem => {
    const start = event.startTime || event.time || '00:00'
    const end = event.endTime || start
    return {
        title: event.title,
        description: event.description,
        location: event.location,
        link: event.link,
        start_time: toUnixSeconds(event.date, start),
        end_time: toUnixSeconds(event.endDate ?? event.date, end),
        inform_type: event.informType ?? 'none',
        color: toApiColor(event),
    }
}

const toModifyPayload = (id: number, data: Partial<CalEvent>): CalendarEventModifyItem => {
    const payload: CalendarEventModifyItem = { id }

    if (data.title !== undefined) payload.title = data.title
    if (data.description !== undefined) payload.description = data.description
    if (data.location !== undefined) payload.location = data.location
    if (data.link !== undefined) payload.link = data.link
    if (data.informType !== undefined) payload.inform_type = data.informType

    if (data.date !== undefined || data.startTime !== undefined || data.time !== undefined) {
        const dateKey = data.date ?? toDateKey(new Date())
        const start = data.startTime || data.time || '00:00'
        payload.start_time = toUnixSeconds(dateKey, start)
    }

    if (data.date !== undefined || data.endDate !== undefined || data.endTime !== undefined || data.time !== undefined) {
        const endDateKey = data.endDate ?? data.date ?? toDateKey(new Date())
        const end = data.endTime || data.time || '00:00'
        payload.end_time = toUnixSeconds(endDateKey, end)
    }

    if (data.color !== undefined || data.source !== undefined) {
        payload.color = toApiColor({ color: data.color, source: data.source ?? 'life' })
    }

    return payload
}

const fromApiItem = (item: CalendarEventApiItem): CalEvent => {
    const startDate = fromUnixSeconds(item.start_time)
    const endDate = fromUnixSeconds(item.end_time)
    const sourceTitle = typeof item.source === 'string' ? item.source : item.source.title
    const sourceMeta = typeof item.source === 'string' ? null : item.source
    const startDateKey = toDateKey(startDate)
    const endDateKey = toDateKey(endDate)
    const startTime = toHHMM(startDate)
    const endTime = toHHMM(endDate)

    return {
        id: item.id,
        title: item.title,
        type: 'personal',
        source: sourceTitle || 'life',
        sourceId: sourceMeta?.id,
        sourceVisible: sourceMeta?.is_visible,
        informType: item.inform_type,
        color: colorNameToHex(item.color),
        time: startTime,
        startTime,
        endTime,
        date: startDateKey,
        endDate: endDateKey !== startDateKey ? endDateKey : undefined,
        location: item.location,
        description: item.description,
        link: item.link,
    }
}

/** 获取源列表 GET /events/sources */
export async function getCalendarSources (): Promise<CalendarSourceItem[]> {
    const rows = await http.get<CalendarSourceItem[]>('/events/sources')
    return Array.isArray(rows) ? rows : []
}

/** 日程查询 GET /events */
export async function searchCalendarEvents (query: CalendarEventQuery): Promise<CalEvent[]> {
    const response = await http.request<CalendarEventListResponse>({
        url: '/events',
        method: 'get',
        data: query,
    })
    const rows = Array.isArray(response?.data) ? response.data : []
    return rows.map(fromApiItem)
}

/** 兼容旧调用：按条件查询日程 */
export async function getCalendarEvents (params?: { start?: string; end?: string; source?: string }): Promise<CalEvent[]> {
    if (!params) return searchCalendarEvents({})

    const query: CalendarEventQuery = {}
    if (params.start) query.start_time = Math.floor(new Date(`${params.start}T00:00:00`).getTime() / 1000)
    if (params.end) query.end_time = Math.floor(new Date(`${params.end}T23:59:59`).getTime() / 1000)
    if (params.source) query.source = params.source

    return searchCalendarEvents(query)
}

/** 创建日程 POST /events/create */
export async function createCalendarEvent (data: Omit<CalEvent, 'id'>): Promise<CalEvent> {
    const payload = [toCreatePayload(data)]
    const response = await http.post<CalendarCreateResponse>('/events/create', payload)
    const firstId = response?.ids?.[0]

    if (!firstId) {
        return { id: Date.now(), ...data }
    }

    const rows = await searchCalendarEvents({ id: firstId })
    return rows[0] ?? { id: firstId, ...data }
}

/** 修改日程 PUT /events/modify */
export async function updateCalendarEvent (id: number, data: Partial<CalEvent>): Promise<CalendarMessageResponse> {
    const payload = [toModifyPayload(id, data)]
    return http.put<CalendarMessageResponse>('/events/modify', payload)
}

/** 删除日程 DELETE /events/delete */
export async function deleteCalendarEvent (id: number): Promise<CalendarMessageResponse> {
    return http.delete<CalendarMessageResponse>('/events/delete', { data: [id] })
}

// ─── Mock Data (临时占位，后端就绪后移除) ──────────────────────────────────────
export function buildDefaultEvents (): CalEvent[] {
    const today = new Date()
    const fmt = (d: Date) => toDateKey(d)
    const off = (n: number) => { const d = new Date(today); d.setDate(d.getDate() + n); return d }

    return [
        { id: 1, title: 'Software Engineering Lecture', type: 'class', source: 'course', color: '#3b82f6', time: '08:00', startTime: '08:00', endTime: '09:45', date: fmt(today), location: 'Teaching Building 1, Room 201', courseId: 'CS304', description: 'Weekly lecture on architecture and requirement analysis.', link: 'https://lms.example.edu/cs304' },
        { id: 2, title: 'Algorithm Midterm Exam', type: 'exam', source: 'course', color: '#ef4444', time: '10:00', startTime: '10:00', endTime: '12:00', date: fmt(today), location: 'Gym Hall A', courseId: 'CS302', description: 'Bring student ID and calculator.', link: 'https://lms.example.edu/cs302/exam' },
        { id: 3, title: 'Project Submission Deadline', type: 'deadline', source: 'work', color: '#ef4444', time: '23:59', startTime: '23:59', date: fmt(today), courseId: 'CS304', description: 'Submit final report and repository URL.', link: 'https://github.com/org/team-project' },
        { id: 4, title: 'Study Group Meeting', type: 'personal', source: 'life', color: '#f59e0b', time: '14:00', startTime: '14:00', endTime: '15:00', date: fmt(today), location: 'Library Room B204', description: 'Discuss week 6 topics and assign exercises.' },
        { id: 5, title: 'Linear Algebra Lecture', type: 'class', source: 'course', color: '#14b8a6', time: '08:00', startTime: '08:00', endTime: '09:40', date: fmt(off(1)), location: 'Teaching Building 2, Room 101', courseId: 'MA201' },
        { id: 6, title: 'Database Assignment Due', type: 'deadline', source: 'work', color: '#3b82f6', time: '23:59', startTime: '23:59', date: fmt(off(1)), courseId: 'CS307', link: 'https://lms.example.edu/cs307/assignments/3' },
        { id: 7, title: 'Physics Lab', type: 'class', source: 'course', color: '#14b8a6', time: '14:00', startTime: '14:00', endTime: '16:00', date: fmt(off(2)), location: 'Lab Building 3', courseId: 'PH101' },
        { id: 8, title: 'Mid-term Exam Review', type: 'personal', source: 'life', color: '#3b82f6', time: '19:00', startTime: '19:00', endTime: '20:00', date: fmt(off(3)), location: 'Self-study Room 4' },
        { id: 9, title: 'Operating Systems Lecture dsadsajkldsahkjfhjkdsa', type: 'class', source: 'course', color: '#3b82f6', time: '10:00', startTime: '10:00', endTime: '11:40', date: fmt(off(4)), courseId: 'CS301' },
        { id: 10, title: 'Final Exam - Algorithms', type: 'exam', source: 'course', color: '#ef4444', time: '09:00', startTime: '09:00', endTime: '11:00', date: fmt(off(7)), location: 'Main Exam Hall', courseId: 'CS302' },
        { id: 11, title: 'Project Presentation', type: 'deadline', source: 'work', color: '#3b82f6', time: '16:00', startTime: '16:00', endTime: '17:00', date: fmt(off(5)), courseId: 'CS304', location: 'Room 101' },
        { id: 12, title: 'Club Activity', type: 'personal', source: 'club', color: '#f59e0b', time: '18:00', startTime: '18:00', endTime: '20:00', date: fmt(off(-2)), description: 'Weekly board-game night.' },
    ]
}
