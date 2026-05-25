import http from '@/utils/http'

export type NotificationLevel = 'info' | 'success' | 'warning' | 'error'

export interface NotificationActionRequest {
    title: string
    deeplink?: string | null
}

export interface NotificationDispatchRequest {
    title: string
    message: string
    level?: NotificationLevel
    deeplink?: string | null
    actions?: NotificationActionRequest[]
    thread?: string | null
    timeout_s?: number | null
}

export interface NotificationDispatchResponse {
    status: 'scheduled'
    notification_id: string | null
}

export interface NotificationDeeplinkPreviewResponse {
    deeplink: string
}

export function dispatchNotification (payload: NotificationDispatchRequest): Promise<NotificationDispatchResponse> {
    return http.post<NotificationDispatchResponse>('/notifications/dispatch', payload)
}

export function previewNotificationDeeplink (
    resource: string,
    params?: {
        entity_id?: string
        action?: string
        tab?: string
    },
): Promise<NotificationDeeplinkPreviewResponse> {
    return http.get<NotificationDeeplinkPreviewResponse>(
        `/notifications/deeplink-preview/${encodeURIComponent(resource)}`,
        { params },
    )
}
