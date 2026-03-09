import http, { baseURL } from '@/utils/http'

/** 生成 UUID v4，兼容非 HTTPS 环境 */
export function generateUUID (): string {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
        return crypto.randomUUID()
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = Math.random() * 16 | 0
        const v = c === 'x' ? r : (r & 0x3 | 0x8)
        return v.toString(16)
    })
}

// --- Interfaces based on the document ---

/**
 * 会话 (Conversation)
 */
export interface Conversation {
    /** 会话ID */
    conversation_id: string;
    /** 会话创建时间 */
    created_at: number;
    /** 会话更新时间 */
    updated_at: number;
    /** 会话标题 */
    title: string;
    /** 会话是否进行中 */
    is_active: boolean;
    /** 会话是否置顶 */
    is_pinned: boolean;
}

/**
 * 会话列表响应 (Conversation List Response)
 */
export interface ConversationListResponse {
    conversations: Conversation[];
}

/**
 * 搜索会话响应 (Search Conversation Response)
 */
export interface SearchConversationResponse {
    conversations: Conversation[];
    sessions?: any[];
}

/**
 * 通用消息响应
 */
export interface MessageResponse {
    message: string;
}

// --- SSE Event Types ---

/** SSE 事件名称 */
export type SseEventName =
    | 'history'
    | 'thought_step'
    | 'message_delta'
    | 'done'
    | 'error'
    | 'keep_alive'
    | 'set_title'

/** thought_step 中 step 的类型 */
export type ThoughtStepType = 'thought_step' | 'tool_call' | 'tool_response'

/** 思维步骤 */
export interface ThoughtStep {
    id: string;
    type: ThoughtStepType;
    content: string;
    status: string;
    created_at: number;
    raw_json: string;
}

/** 历史消息条目 */
export interface HistoryMessage {
    message_id: string;
    content: string;
    parent: string | null;
    role: 'system' | 'user' | 'assistant' | 'tool';
    created_at: number;
    thought_steps: ThoughtStep[];
}

/** event: history — 历史消息列表 */
export interface SseHistoryData {
    history_messages: HistoryMessage[] | null;
}

/** event: message_delta — 流式内容片段 */
export interface SseMessageDeltaData {
    message_id: string;
    delta: string;
    /** message start 时与 message_id 一并返回 */
    request_id?: string;
}

/** event: thought_step — 思维/工具步骤 */
export interface SseThoughtStepData {
    message_id: string;
    step: ThoughtStep;
}

/** event: done — 一次消息结束 */
export interface SseDoneData {
    conversation_id: string;
    message_id: string;
    created_at: number;
    updated_at: number;
    is_active: boolean;
    is_pinned: boolean;
}

/** event: error — 流内传输错误 */
export interface SseErrorData {
    error_message: string;
}

/** event: set_title — 设置会话标题 */
export interface SseSetTitleData {
    conversation_id: string;
    title: string;
}

/** SSE 原始 event 帧（泛型） */
export interface SseFrame<T = unknown> {
    event: SseEventName;
    data: T;
    id?: string;
}

/**
 * SSE 事件回调集合
 * 消费方按需传入需要处理的事件即可
 */
export interface SseHandlers {
    onHistory?: (data: SseHistoryData) => void;
    onThoughtStep?: (data: SseThoughtStepData) => void;
    onMessageDelta?: (data: SseMessageDeltaData) => void;
    onDone?: (data: SseDoneData) => void;
    onError?: (data: SseErrorData) => void;
    onSetTitle?: (data: SseSetTitleData) => void;
    /** 连接/网络层错误 */
    onFetchError?: (err: unknown) => void;
}

// --- API Methods ---

/**
 * 发起聊天接口：创建新会话，返回 conversation_id
 * POST /conversation
 */
export function createConversation (): Promise<Conversation> {
    return http.post<Conversation>('/conversation')
}

/**
 * 获取历史对话列表
 * GET /conversations/
 */
export function getConversations (params?: { page?: number; pageSize?: number }) {
    return http.get<ConversationListResponse>('/conversations/', { params });
}

/**
 * 历史对话搜索
 * GET /conversations/search
 */
export function searchConversations (params: { keywords: string; page?: number; page_size?: number }) {
    return http.get<SearchConversationResponse>('/conversations/search', { params });
}

/**
 * 更新对话信息 (置顶或重命名)
 * PATCH /conversation/{conversation_id}
 */
export function updateConversation (conversation_id: string, data: { is_pinned?: boolean; title?: string }) {
    return http.patch<MessageResponse>(`/conversation/${conversation_id}`, data);
}

/**
 * 删除对话
 * DELETE /conversation/{conversation_id}
 */
export function deleteConversation (conversation_id: string) {
    return http.delete<MessageResponse>(`/conversation/${conversation_id}`);
}

/**
 * 流式聊天补全接口
 * POST /conversation/completion  (multipart/form-data, text/event-stream)
 *
 * 使用原生 fetch + ReadableStream 处理 SSE，
 * 返回 AbortController，调用方可随时调用 abort() 停止流。
 */
export function chatCompletion (
    payload: {
        conversation_id: string;
        request_id: string;
        content?: string;
        create_at: number;
        attachments?: string[];
        need_history?: boolean;
    },
    handlers: SseHandlers
): AbortController {
    const controller = new AbortController()

    const form = new FormData()
    form.append('conversation_id', payload.conversation_id)
    form.append('request_id', payload.request_id)
    form.append('create_at', String(payload.create_at))
    if (payload.content !== undefined) form.append('content', payload.content)
    if (payload.need_history !== undefined) form.append('need_history', String(payload.need_history))
    if (payload.attachments) {
        payload.attachments.forEach(id => form.append('attachments', id))
    }

    ; (async () => {
        try {
            const response = await fetch(`${baseURL}/conversation/completion`, {
                method: 'POST',
                body: form,
                signal: controller.signal,
            })

            if (!response.ok || !response.body) {
                handlers.onFetchError?.(new Error(`HTTP ${response.status}`))
                return
            }

            const reader = response.body.getReader()
            const decoder = new TextDecoder()

            // SSE 解析状态
            let buffer = ''
            let currentEvent = ''
            let currentData = ''

            const processFrame = () => {
                if (!currentData) return
                try {
                    const parsed = JSON.parse(currentData)
                    switch (currentEvent as SseEventName) {
                        case 'history':
                            handlers.onHistory?.(parsed as SseHistoryData)
                            break
                        case 'thought_step':
                            handlers.onThoughtStep?.(parsed as SseThoughtStepData)
                            break
                        case 'message_delta':
                            handlers.onMessageDelta?.(parsed as SseMessageDeltaData)
                            break
                        case 'done':
                            handlers.onDone?.(parsed as SseDoneData)
                            break
                        case 'error':
                            handlers.onError?.(parsed as SseErrorData)
                            break
                        case 'set_title':
                            handlers.onSetTitle?.(parsed as SseSetTitleData)
                            break
                    }
                } catch (e) {
                    console.warn('[SSE] JSON parse error:', currentData, e)
                }
                currentEvent = ''
                currentData = ''
            }

            while (true) {
                const { value, done } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split('\n')
                buffer = lines.pop() ?? ''

                for (const line of lines) {
                    if (line.startsWith('event:')) {
                        currentEvent = line.slice(6).trim()
                    } else if (line.startsWith('data:')) {
                        currentData = line.slice(5).trim()
                    } else if (line === '') {
                        // 空行 → 分发一帧
                        processFrame()
                    }
                }
            }
            // 处理末尾残余
            processFrame()
        } catch (err) {
            if ((err as DOMException)?.name !== 'AbortError') {
                handlers.onFetchError?.(err)
            }
        }
    })()

    return controller
}
