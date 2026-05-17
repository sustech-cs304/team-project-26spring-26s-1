export interface OpenAIModelEndpointDraft {
    baseUrl: string
    apiKey: string
}

export function getOpenAIModelsUrl (baseUrl: string) {
    const normalized = baseUrl.trim().replace(/\/+$/, '')
    if (!normalized) return ''
    const baseWithVersion = normalized.endsWith('/v1') ? normalized : `${normalized}/v1`
    return `${baseWithVersion}/models`
}

export function parseOpenAIModelIds (payload: unknown) {
    if (!payload || typeof payload !== 'object') return []

    const maybeData = (payload as { data?: unknown }).data
    const list = Array.isArray(maybeData)
        ? maybeData
        : Array.isArray(payload)
            ? payload
            : []

    return Array.from(new Set(list
        .map((item) => {
            if (typeof item === 'string') return item
            if (item && typeof item === 'object' && typeof (item as { id?: unknown }).id === 'string') {
                return (item as { id: string }).id
            }
            return ''
        })
        .map(item => item.trim())
        .filter(Boolean)))
}

export async function requestOpenAIModels (endpoint: OpenAIModelEndpointDraft, label = '模型') {
    const url = getOpenAIModelsUrl(endpoint.baseUrl)
    const apiKey = endpoint.apiKey.trim()

    if (!url || !apiKey) {
        throw new Error(`请先填写${label}的 Base URL 和 API Key`)
    }

    const response = await fetch(url, {
        method: 'GET',
        headers: {
            Accept: 'application/json',
            Authorization: `Bearer ${apiKey}`,
        },
    })

    const payload = await response.json().catch(() => null)
    if (!response.ok) {
        const message = payload && typeof payload === 'object'
            ? ((payload as { error?: { message?: string }, message?: string }).error?.message
                || (payload as { message?: string }).message)
            : ''
        throw new Error(message || `${label}连接失败（${response.status}）`)
    }

    return parseOpenAIModelIds(payload)
}
