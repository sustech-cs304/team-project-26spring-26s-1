import http from '@/utils/http'
import type { CalEvent, CalendarCreateResponse, CalendarEventApiItem, CalendarEventCreateItem, CalendarEventListResponse,
 CalendarEventModifyItem, CalendarEventQuery, CalendarMessageResponse, CalendarSourceItem, CalendarSourceUpdate } from '@/types/calendar'
import { toDateKey, toUnixSecondsByDateKey } from '@/utils/calendar'

export type {CalendarEventQuery,CalendarSourceItem,CalendarSourceUpdate,}

const fromUnixSeconds = (value: number): Date => new Date(value * 1000)

const toHHMM = (date: Date): string => {
    const hh = `${date.getHours()}`.padStart(2, '0')
    const mm = `${date.getMinutes()}`.padStart(2, '0')
    return `${hh}:${mm}`
}

const toApiColor = (event: Pick<CalEvent, 'color' | 'source'>): string => {
    const raw = `${event.color ?? ''}`.trim()
    if (raw) return raw
    return '#2563eb'
}

const toCreatePayload = (event: Omit<CalEvent, 'id'>): CalendarEventCreateItem => {
    const start = event.startTime || event.time || '00:00'
    const end = event.endTime || start
    return {
        title: event.title,
        description: event.description,
        location: event.location,
        link: event.link,
        start_time: toUnixSecondsByDateKey(event.date, start),
        end_time: toUnixSecondsByDateKey(event.endDate ?? event.date, end),
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
        payload.start_time = toUnixSecondsByDateKey(dateKey, start)
    }

    if (data.date !== undefined || data.endDate !== undefined || data.endTime !== undefined || data.time !== undefined) {
        const endDateKey = data.endDate ?? data.date ?? toDateKey(new Date())
        const end = data.endTime || data.time || '00:00'
        payload.end_time = toUnixSecondsByDateKey(endDateKey, end)
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
        source: sourceTitle || 'life',
        sourceId: sourceMeta?.id,
        sourceVisible: sourceMeta?.is_visible,
        informType: item.inform_type,
        color: `${item.color ?? ''}`.trim() || '#2563eb',
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

/** 更新源信息 PATCH /events/sources/{source_id} */
export async function updateCalendarSource (sourceId: number, payload: CalendarSourceUpdate): Promise<CalendarSourceItem> {
    return http.patch<CalendarSourceItem>(`/events/sources/${sourceId}`, payload)
}

/** 日程查询 GET /events */
export async function searchCalendarEvents (query: CalendarEventQuery): Promise<CalEvent[]> {
    const response = await http.get<CalendarEventListResponse>('/events', { params: query })
    const rows = Array.isArray(response?.data) ? response.data : []
    return rows.map(fromApiItem)
}

/** 兼容旧调用：按条件查询日程 */
export async function getCalendarEventById (id: number): Promise<CalEvent | null> {
    const rows = await searchCalendarEvents({ id })
    return rows[0] ?? null
}

export async function getCalendarEvents (params?: { start?: string; end?: string; source?: string }): Promise<CalEvent[]> {
    if (!params) return searchCalendarEvents({})

    const query: CalendarEventQuery = {}
    if (params.start) query.start_time = toUnixSecondsByDateKey(params.start, '00:00')
    if (params.end) query.end_time = toUnixSecondsByDateKey(params.end, '23:59')
    if (params.source) query.source = params.source

    return searchCalendarEvents(query)
}

/** 创建日程 POST /events/create */
export async function createCalendarEvent (data: Omit<CalEvent, 'id'>): Promise<CalEvent> {
    const payload = [toCreatePayload(data)]
    const response = await http.post<CalendarCreateResponse>('/events/create', payload)
    const firstId = response?.ids?.[0]

    return { id: firstId ?? Date.now(), ...data }
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
