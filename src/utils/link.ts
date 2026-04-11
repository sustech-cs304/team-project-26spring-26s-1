import { invoke } from '@tauri-apps/api/core'
import router from '@/router'

const isTauriClient = () => typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

const shouldHandleHref = (href: string): boolean => {
    const normalized = href.trim().toLowerCase()
    if (!normalized) return false
    if (normalized.startsWith('#')) return false
    if (normalized.startsWith('javascript:')) return false
    return true
}

const toAbsoluteUrl = (href: string): string => {
    return new URL(href, window.location.href).toString()
}

type LinkTarget = 'internal' | 'external'

const resolveLinkTarget = (href: string): { url: string, target: LinkTarget } | null => {
    try {
        const url = toAbsoluteUrl(href)
        const parsed = new URL(url)
        const protocol = parsed.protocol.toLowerCase()

        if (protocol === 'mailto:' || protocol === 'tel:') {
            return { url, target: 'external' }
        }

        if (protocol === 'http:' || protocol === 'https:') {
            const target: LinkTarget = parsed.origin === window.location.origin ? 'internal' : 'external'
            return { url, target }
        }

        return null
    } catch {
        return null
    }
}

export const openExternalLink = async (href: string): Promise<void> => {
    if (!shouldHandleHref(href)) return

    const resolved = resolveLinkTarget(href)
    if (!resolved || resolved.target !== 'external') return
    const { url } = resolved

    if (isTauriClient()) {
        try {
            await invoke('open_external_link', { url })
            return
        } catch (error) {
            console.warn('[link] failed to open by tauri command, fallback to window.open:', error)
        }
    }

    window.open(url, '_blank', 'noopener,noreferrer')
}

export const installGlobalLinkHandler = (): void => {
    document.addEventListener('click', (event) => {
        const mouseEvent = event as MouseEvent
        if (mouseEvent.defaultPrevented) return
        if (mouseEvent.button !== 0) return
        if (mouseEvent.metaKey || mouseEvent.ctrlKey || mouseEvent.shiftKey || mouseEvent.altKey) return

        const target = mouseEvent.target as Element | null
        const anchor = target?.closest('a[href]') as HTMLAnchorElement | null
        if (!anchor) return

        const href = anchor.getAttribute('href') || ''
        if (!shouldHandleHref(href)) return
        const resolved = resolveLinkTarget(href)
        if (!resolved) return

        event.preventDefault()

        if (resolved.target === 'internal') {
            const parsed = new URL(resolved.url)
            const path = `${parsed.pathname}${parsed.search}${parsed.hash}`
            if (path !== `${window.location.pathname}${window.location.search}${window.location.hash}`) {
                void router.push(path)
            }
            return
        }

        void openExternalLink(href)
    })
}
