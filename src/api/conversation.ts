import http, { baseURL } from '@/utils/http'
import type {
    Conversation, ConversationListResponse, SearchConversationResponse, MessageResponse, SseHandlers, SseHistoryResponse, SseMessageDeltaData, SseToolCallData, SseErrorData, SseKeepAliveData, SseDoneData,
    SseEventTypes,
    SseMetaData
} from '@/types/conversation.ts'

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
        message_id?: string;
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
    if (payload.message_id !== undefined) form.append('message_id', payload.message_id)
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
                    switch (currentEvent as SseEventTypes) {
                        case 'history':
                            handlers.onHistory?.(parsed as SseHistoryResponse)
                            break
                        case 'delta':
                            handlers.onDelta?.(parsed as SseMessageDeltaData)
                            break
                        case 'meta_data':
                            handlers.onMetaData?.(parsed as SseMetaData)
                            break
                        case 'tool_call':
                            handlers.onToolCall?.(parsed as SseToolCallData)
                            break
                        case 'error':
                            handlers.onError?.(parsed as SseErrorData)
                            break
                        case 'done':
                            handlers.onDone?.(parsed as SseDoneData)
                            break
                        case 'keep_alive':
                            handlers.onKeepAlive?.(parsed as SseKeepAliveData)
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
                    const trimmed = line.trim()
                    if (trimmed.startsWith('event:')) {
                        currentEvent = trimmed.slice(6).trim()
                    }
                    else if (trimmed.startsWith('data:')) {
                        const chunk = trimmed.slice(5).trim()
                        currentData += (currentData ? '\n' : '') + chunk
                    }
                    else if (trimmed === '') {
                        processFrame()
                    }
                }
            }
            processFrame()
        } catch (err) {
            if ((err as DOMException)?.name !== 'AbortError') {
                handlers.onFetchError?.(err)
            }
        }
    })()

    return controller
}

/**
 * 停止对话接口：通知后端终止当前对话流并更新状态
 * POST /conversation/cancelchat
 */
export function cancelChat (conversation_id: string, message_id: string): Promise<MessageResponse> {
    return http.post<MessageResponse>('/conversation/cancelchat', null, {
        params: { conversation_id, message_id },
    })
}
