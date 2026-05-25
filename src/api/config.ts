import http from '@/utils/http'

export type LLMProviderType = 'OpenAI' | 'Qwen' | 'Anthropic'

export interface LLMEndpointConfig {
    type: LLMProviderType
    base_url: string
    api_key: string
    model: string
    max_token_count: number
}

export interface RerankerEndpointConfig {
    type: 'OpenAI'
    base_url: string
    api_key: string
    model: string
}

export interface EmbedEndpointConfig {
    type: 'OpenAI'
    base_url: string
    api_key: string
    model: string
    dims: number
}

export interface ASREndpointConfig {
    type: 'Qwen'
    base_url: string
    api_key: string
}

export interface FileConfig {
    upload_path: string
    rag_path: string
    mineru: {
        base_url: string
        api_key: string
    }
}

export interface WebFetchConfig {
    base_url: string
    api_key: string
    path: string
    timeout_ms: number
}

export interface OneBotConfig {
    token: string
    superuser_ids: string[]
}

export interface TelegramConfig {
    token: string
    superuser_ids: string[]
}

export interface RagCloudConfig {
    base_url: string
    manifest_path: string
    timeout_ms: number
    api_key: string
}

export interface SkillsCloudConfig {
    base_url: string
    timeout_ms: number
    delete_submission_path: string
    local_store_path: string
}

export interface NotificationConfig {
    enabled: boolean
    app_name: string
    app_icon: string | null
    notification_limit: number | null
    default_timeout_s: number
    deeplink_scheme: string
    task_complete: boolean
    task_failed: boolean
    calendar_reminder: boolean
}

export interface CodeInterpreterConfig {
    default_timeout_s: number
}

export type MCPTransportType = 'http' | 'stdio'

export interface MCPConfig {
    transport: MCPTransportType
    url: string | null
    token: string | null
    command: string | null
    args: string[]
    env: Record<string, string>
    cwd: string | null
    enabled: boolean
}

export interface ApiConfig {
    agent: LLMEndpointConfig
    utility: LLMEndpointConfig
    embed: EmbedEndpointConfig
    rerank: RerankerEndpointConfig
    asr: ASREndpointConfig
}

export interface AppConfig {
    api: ApiConfig
    file: FileConfig
    webfetch: WebFetchConfig
    websearch: WebFetchConfig
    onebot: OneBotConfig
    telegram?: TelegramConfig
    rag_cloud: RagCloudConfig
    skills_cloud: SkillsCloudConfig
    notification: NotificationConfig
    code_interpreter: CodeInterpreterConfig
    mcp: Record<string, MCPConfig>
}

export type DeepPartial<T> = T extends Array<infer U>
    ? Array<DeepPartial<U>>
    : T extends object
        ? {
            [K in keyof T]?: DeepPartial<T[K]>
        }
        : T

export function getConfig(): Promise<AppConfig> {
    return http.get<AppConfig>('/get_config')
}

export function patchConfig(delta: DeepPartial<AppConfig>): Promise<AppConfig> {
    return http.patch<AppConfig>('/patch_config', delta)
}
