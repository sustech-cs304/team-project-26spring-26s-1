import { invoke } from '@tauri-apps/api/core'
import router from '@/router'

const DEEPLINK_EVENT = 'app://deeplink'
const NOTIFICATION_EVENT = 'app://notification-request'

type DeeplinkSource = 'launch' | 'protocol' | 'notification' | 'notification-action'

type DeeplinkEventPayload = {
  url: string
  source: DeeplinkSource
}

type NotificationActionPayload = {
  title: string
  deeplink?: string | null
}

type DispatchNotificationPayload = {
  title: string
  message: string
  level?: 'info' | 'success' | 'warning' | 'error'
  deeplink?: string | null
  actions?: NotificationActionPayload[]
  thread?: string | null
  timeout_s?: number | null
}

const isTauriClient = () => typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

const normalizeResource = (url: URL): { resource: string; entityId: string | null } => {
  const resource = url.host.trim().toLowerCase()
  const pathname = url.pathname.replace(/^\/+/, '')
  const entityId = pathname ? pathname.split('/')[0] || null : null
  return { resource, entityId }
}

const toQueryObject = (searchParams: URLSearchParams): Record<string, string> => {
  const query: Record<string, string> = {}
  for (const [key, value] of searchParams.entries()) {
    query[key] = value
  }
  return query
}

const mapDeeplinkToRoute = (rawUrl: string) => {
  const parsed = new URL(rawUrl)
  const query = toQueryObject(parsed.searchParams)
  const { resource, entityId } = normalizeResource(parsed)

  switch (resource) {
    case 'home':
      return { path: '/', query }
    case 'conversations':
      return { path: entityId ? `/c/${entityId}` : '/c', query }
    case 'tasks':
      return {
        path: '/tasks',
        query: {
          ...query,
          ...(entityId ? { taskId: entityId } : {}),
        },
      }
    case 'runs':
      return {
        path: '/tasks',
        query: {
          ...query,
          ...(entityId ? { runId: entityId } : {}),
        },
      }
    case 'calendar':
      return {
        path: '/calendar',
        query: {
          ...query,
          ...(entityId ? { eventId: entityId } : {}),
        },
      }
    case 'settings':
      return {
        path: '/settings',
        query: {
          ...query,
          ...(entityId ? { tab: entityId } : {}),
        },
      }
    default:
      return { path: '/', query }
  }
}

export const handleDeepLinkUrl = async (rawUrl: string): Promise<void> => {
  const value = rawUrl.trim()
  if (!value.toLowerCase().startsWith('opencrab://')) return

  try {
    const target = mapDeeplinkToRoute(value)
    const current = router.currentRoute.value
    const currentFullPath = current.fullPath
    const next = router.resolve(target)
    if (next.fullPath !== currentFullPath) {
      await router.push(target)
    }
  } catch (error) {
    console.warn('[deeplink] failed to handle url:', value, error)
    if (router.currentRoute.value.path !== '/') {
      await router.push('/')
    }
  }
}

const showBrowserNotification = async (payload: DispatchNotificationPayload): Promise<void> => {
  if (typeof window === 'undefined' || typeof Notification === 'undefined') return

  if (Notification.permission === 'default') {
    try {
      await Notification.requestPermission()
    } catch (error) {
      console.warn('[notification] permission request failed:', error)
    }
  }

  if (Notification.permission !== 'granted') return

  const notification = new Notification(payload.title, {
    body: payload.message,
    tag: payload.thread ?? undefined,
  })

  if (payload.timeout_s && payload.timeout_s > 0) {
    window.setTimeout(() => notification.close(), payload.timeout_s * 1000)
  }

  notification.onclick = () => {
    notification.close()
    window.focus()
    const deeplink = payload.deeplink || payload.actions?.find((action) => action.deeplink)?.deeplink
    if (deeplink) {
      void handleDeepLinkUrl(deeplink)
    }
  }
}

const installNotificationHandler = async (): Promise<void> => {
  if (!isTauriClient()) return

  const { listen } = await import('@tauri-apps/api/event')
  await listen<DispatchNotificationPayload>(NOTIFICATION_EVENT, (event) => {
    void showBrowserNotification(event.payload)
  })
}

const installEventListener = async (): Promise<void> => {
  if (!isTauriClient()) return

  const { listen } = await import('@tauri-apps/api/event')
  await listen<DeeplinkEventPayload>(DEEPLINK_EVENT, (event) => {
    void handleDeepLinkUrl(event.payload.url)
  })
}

const consumePendingDeeplinks = async (): Promise<void> => {
  if (!isTauriClient()) return

  const pending = await invoke<DeeplinkEventPayload[]>('consume_pending_deeplinks')
  for (const item of pending) {
    await handleDeepLinkUrl(item.url)
  }
}

export const installDeepLinkHandler = async (): Promise<void> => {
  await installEventListener()
  await installNotificationHandler()
  await consumePendingDeeplinks()
}
