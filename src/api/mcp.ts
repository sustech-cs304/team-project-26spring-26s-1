import { baseURL } from '@/utils/http'

export interface McpServerStatus {
    name: string
    status: string
}

function withTimeout (timeoutMs: number) {
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), timeoutMs)

    return {
        signal: controller.signal,
        cleanup: () => window.clearTimeout(timer),
    }
}

function buildMcpStatusURL (): string {
    const backendOrigin = new URL(baseURL, window.location.origin).origin
    return new URL('/mcp', `${backendOrigin}/`).toString()
}

export async function getMcpStatuses (): Promise<McpServerStatus[]> {
    const request = withTimeout(1200)

    try {
        const response = await fetch(buildMcpStatusURL(), {
            method: 'GET',
            cache: 'no-store',
            credentials: 'include',
            headers: {
                Accept: 'application/json',
            },
            signal: request.signal,
        })

        if (!response.ok) {
            throw new Error(`MCP status request failed (${response.status})`)
        }

        const payload = await response.json()
        return Array.isArray(payload) ? payload as McpServerStatus[] : []
    } finally {
        request.cleanup()
    }
}
