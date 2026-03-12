// conversation types

export type StepStatus = 'running' | 'done' | 'error'

export interface Message {
    role: 'user' | 'assistant'
    content: string
    created_at: number
    thinkingSteps?: ThoughtStep[]
    thinkingActive?: boolean
    message_id?: string
}

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

export type StepType = 'search' | 'code' | 'tool' | 'read' | 'think' | 'api' | 'thought_step' | 'tool_call' | 'tool_response'

/** 思维步骤 */
export interface ThoughtStep {
    id: string;
    type: StepType;
    title?: string;
    content?: string;
    status: StepStatus;
    created_at?: number;
    raw_json?: string;
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
