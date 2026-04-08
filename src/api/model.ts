import http from '@/utils/http'

export interface TestModelConnectionPayload {
    provider: 'OpenAI' | 'DeepSeek' | 'Local Ollama'
    baseUrl: string
    apiKey: string
    modelName: string
}

export interface TestModelConnectionResponse {
    success: boolean
    message?: string
    latencyMs?: number
}

export const MODEL_CONNECTION_TEST_ENDPOINT = '/model/test-connection'

export function testModelConnection (payload: TestModelConnectionPayload): Promise<TestModelConnectionResponse> {
    return http.post<TestModelConnectionResponse>(MODEL_CONNECTION_TEST_ENDPOINT, payload)
}
