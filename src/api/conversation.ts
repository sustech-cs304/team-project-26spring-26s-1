import http from '@/utils/http'

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
 * Note: The document example shows `sessions` with camelCase fields (sessionID, createdAt...),
 * but typical consistency suggests snake_case. Since the doc is contradictory (schema vs example),
 * we define based on the schema `会话列表` which uses snake_case and `conversations`.
 * However, if the search endpoint specifically returns `sessions` we should support that.
 * The schema table for search says "会话列表" as return model, which implies `conversations`.
 * We will use `conversations` as primary but keep in mind backend might vary.
 */
export interface SearchConversationResponse {
    // Aligning with the "会话列表" schema in the doc
    conversations: Conversation[];
    // If the backend returns `sessions` instead as per example:
    sessions?: any[];
}

/**
 * 通用消息响应
 */
export interface MessageResponse {
    message: string;
}

// --- API Methods ---

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
