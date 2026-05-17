import { baseURL } from '@/utils/http'

function withTimeout (timeoutMs: number) {
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), timeoutMs)

    return {
        signal: controller.signal,
        cleanup: () => window.clearTimeout(timer),
    }
}

export async function checkBackendHealth (): Promise<boolean> {
    const healthURL = `${baseURL}/health`

    const request = withTimeout(500)

    try {
        const response = await fetch(healthURL, {
            method: 'GET',
            cache: 'no-store',
            credentials: 'include',
            headers: {
                Accept: 'application/json',
            },
            signal: request.signal,
        })

        if (response.ok) return true
    } finally {
        request.cleanup()
    }

    return false
}
