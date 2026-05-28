export interface OpenAIModelEndpointDraft {
    baseUrl: string
    apiKey: string
}

export interface ChatModelEndpointDraft extends OpenAIModelEndpointDraft {
    provider: 'OpenAI' | 'Qwen' | 'Anthropic'
    model: string
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

function getAnthropicModelsUrl (baseUrl: string) {
    const normalized = baseUrl.trim().replace(/\/+$/, '')
    if (!normalized) return ''
    const baseWithVersion = normalized.endsWith('/v1') ? normalized : `${normalized}/v1`
    return `${baseWithVersion}/models`
}

export async function requestAnthropicModels (endpoint: OpenAIModelEndpointDraft, label = '模型') {
    const url = getAnthropicModelsUrl(endpoint.baseUrl)
    const apiKey = endpoint.apiKey.trim()

    if (!url || !apiKey) {
        throw new Error(`请先填写${label}的 Base URL 和 API Key`)
    }

    const response = await fetch(url, {
        method: 'GET',
        headers: {
            Accept: 'application/json',
            'x-api-key': apiKey,
            'anthropic-version': '2023-06-01',
            'anthropic-dangerous-direct-browser-access': 'true',
        },
    })

    const payload = await response.json().catch(() => null)
    if (!response.ok) {
        throw new Error(readProviderErrorMessage(payload) || `${label}连接失败（${response.status}）`)
    }

    return parseOpenAIModelIds(payload)
}

function getOpenAIChatCompletionsUrl (baseUrl: string) {
    const normalized = baseUrl.trim().replace(/\/+$/, '')
    if (!normalized) return ''
    const baseWithVersion = normalized.endsWith('/v1') ? normalized : `${normalized}/v1`
    return `${baseWithVersion}/chat/completions`
}

function getAnthropicMessagesUrl (baseUrl: string) {
    const normalized = baseUrl.trim().replace(/\/+$/, '')
    if (!normalized) return ''
    const baseWithVersion = normalized.endsWith('/v1') ? normalized : `${normalized}/v1`
    return `${baseWithVersion}/messages`
}

function readProviderErrorMessage (payload: unknown) {
    if (!payload || typeof payload !== 'object') return ''
    const data = payload as {
        error?: { message?: string, error?: { message?: string } } | string
        message?: string
    }
    if (typeof data.error === 'string') return data.error
    return data.error?.message || data.error?.error?.message || data.message || ''
}

function assertChatEndpointDraft (endpoint: ChatModelEndpointDraft, label: string) {
    if (!endpoint.baseUrl.trim() || !endpoint.apiKey.trim() || !endpoint.model.trim()) {
        throw new Error(`请先填写${label}的 Base URL、API Key 和 Model`)
    }
}

async function requestOpenAICompatibleChatCompletion (endpoint: ChatModelEndpointDraft, label: string) {
    const response = await fetch(getOpenAIChatCompletionsUrl(endpoint.baseUrl), {
        method: 'POST',
        headers: {
            Accept: 'application/json',
            Authorization: `Bearer ${endpoint.apiKey.trim()}`,
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            model: endpoint.model.trim(),
            messages: [
                { role: 'user', content: 'hi' },
            ],
            stream: false,
            max_tokens: 16,
        }),
    })

    const payload = await response.json().catch(() => null)
    if (!response.ok) {
        throw new Error(readProviderErrorMessage(payload) || `${label}连接失败（${response.status}）`)
    }
}

async function requestAnthropicMessage (endpoint: ChatModelEndpointDraft, label: string) {
    const response = await fetch(getAnthropicMessagesUrl(endpoint.baseUrl), {
        method: 'POST',
        headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
            'x-api-key': endpoint.apiKey.trim(),
            'anthropic-version': '2023-06-01',
            'anthropic-dangerous-direct-browser-access': 'true',
        },
        body: JSON.stringify({
            model: endpoint.model.trim(),
            messages: [
                { role: 'user', content: 'hi' },
            ],
            stream: false,
            max_tokens: 16,
        }),
    })

    const payload = await response.json().catch(() => null)
    if (!response.ok) {
        throw new Error(readProviderErrorMessage(payload) || `${label}连接失败（${response.status}）`)
    }
}

export async function testChatModelConnection (endpoint: ChatModelEndpointDraft, label = '模型') {
    assertChatEndpointDraft(endpoint, label)

    if (endpoint.provider === 'Anthropic') {
        await requestAnthropicMessage(endpoint, label)
        return
    }

    await requestOpenAICompatibleChatCompletion(endpoint, label)
}
