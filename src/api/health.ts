import { baseURL } from '@/utils/http'

function withTimeout (timeoutMs: number) {
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), timeoutMs)

    return {
        signal: controller.signal,
        cleanup: () => window.clearTimeout(timer),
    }
}

function buildHealthURLs () {
    const apiHealthURL = `${baseURL}/health`

    try {
        const rootHealthURL = new URL(baseURL)
        rootHealthURL.pathname = '/health'
        rootHealthURL.search = ''
        rootHealthURL.hash = ''

        return Array.from(new Set([apiHealthURL, rootHealthURL.toString()]))
    } catch {
        return [apiHealthURL]
    }
}

export async function checkBackendHealth (): Promise<boolean> {
    const healthURLs = buildHealthURLs()

    for (const url of healthURLs) {
        const request = withTimeout(2500)

        try {
            const response = await fetch(url, {
                method: 'GET',
                cache: 'no-store',
                credentials: 'include',
                headers: {
                    Accept: 'application/json',
                },
                signal: request.signal,
            })

            if (response.ok) return true
        } catch {
            // Try the next known health endpoint candidate.
        } finally {
            request.cleanup()
        }
    }

    return false
}
