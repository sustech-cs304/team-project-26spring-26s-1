import http from '@/utils/http'
import type { CalEvent } from '@/utils/calendar'
import { toDateKey } from '@/utils/calendar'

// ─── API Methods ───────────────────────────────────────────────────────────────

/**
 * 获取日历事件列表
 * GET /calendar/events
 */
export function getCalendarEvents (params?: { start?: string; end?: string }): Promise<CalEvent[]> {
    return http.get<CalEvent[]>('/calendar/events', { params })
}

/**
 * 创建日历事件
 * POST /calendar/events
 */
export function createCalendarEvent (data: Omit<CalEvent, 'id'>): Promise<CalEvent> {
    return http.post<CalEvent>('/calendar/events', data)
}

/**
 * 更新日历事件
 * PATCH /calendar/events/{id}
 */
export function updateCalendarEvent (id: number, data: Partial<CalEvent>): Promise<CalEvent> {
    return http.patch<CalEvent>(`/calendar/events/${id}`, data)
}

/**
 * 删除日历事件
 * DELETE /calendar/events/{id}
 */
export function deleteCalendarEvent (id: number): Promise<{ message: string }> {
    return http.delete<{ message: string }>(`/calendar/events/${id}`)
}

// ─── Mock Data (临时占位，后端就绪后移除) ──────────────────────────────────────
export function buildDefaultEvents (): CalEvent[] {
    const today = new Date()
    const fmt = (d: Date) => toDateKey(d)
    const off = (n: number) => { const d = new Date(today); d.setDate(d.getDate() + n); return d }

    return [
        { id: 1, title: 'Software Engineering Lecture', type: 'class', time: '08:00', date: fmt(today), location: 'Teaching Building 1, Room 201', courseId: 'CS304' },
        { id: 2, title: 'Algorithm Midterm Exam', type: 'exam', time: '10:00', date: fmt(today), location: 'Gym Hall A', courseId: 'CS302' },
        { id: 3, title: 'Project Submission Deadline', type: 'deadline', time: '23:59', date: fmt(today), courseId: 'CS304' },
        { id: 4, title: 'Study Group Meeting', type: 'personal', time: '14:00', date: fmt(today), location: 'Library Room B204' },
        { id: 5, title: 'Linear Algebra Lecture', type: 'class', time: '08:00', date: fmt(off(1)), location: 'Teaching Building 2, Room 101', courseId: 'MA201' },
        { id: 6, title: 'Database Assignment Due', type: 'deadline', time: '23:59', date: fmt(off(1)), courseId: 'CS307' },
        { id: 7, title: 'Physics Lab', type: 'class', time: '14:00', date: fmt(off(2)), location: 'Lab Building 3', courseId: 'PH101' },
        { id: 8, title: 'Mid-term Exam Review', type: 'personal', time: '19:00', date: fmt(off(3)), location: 'Self-study Room 4' },
        { id: 9, title: 'Operating Systems Lecture', type: 'class', time: '10:00', date: fmt(off(4)), courseId: 'CS301' },
        { id: 10, title: 'Final Exam - Algorithms', type: 'exam', time: '09:00', date: fmt(off(7)), location: 'Main Exam Hall', courseId: 'CS302' },
        { id: 11, title: 'Project Presentation', type: 'deadline', time: '16:00', date: fmt(off(5)), courseId: 'CS304', location: 'Room 101' },
        { id: 12, title: 'Club Activity', type: 'personal', time: '18:00', date: fmt(off(-2)) },
    ]
}
