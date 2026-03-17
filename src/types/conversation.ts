export interface Conversation {
  conversation_id: string;
  created_at: number;
  updated_at: number;
  title: string;
  is_active: boolean;
  is_pinned: boolean;
}

export interface ConversationListResponse {
  conversations: Conversation[];
}

export interface SearchConversationResponse {
  conversations: Conversation[];
}

export interface MessageResponse {
  message: string;
}

export interface SseFrame<T = unknown> {
  event: 'history' | 'event';
  data: T;
}

export interface SseHandlers {
  onHistory?: (data: SseHistoryResponse) => void;
  onDelta?: (data: SseMessageDeltaData) => void;
  onMetaData?: (data: SseMetaData) => void;
  onToolCall?: (data: SseToolCallData) => void;
  onError?: (data: SseErrorData) => void;
  onKeepAlive?: (data: SseKeepAliveData) => void;
  onDone?: (data: SseDoneData) => void;
  onFetchError?: (error: any) => void;
}

export type SseEventTypes = 'history' | 'delta' | 'meta_data' | 'tool_call' | 'error' | 'done' | 'keep_alive'

export type MsgRole = 'user' | 'assistant' | 'system' | 'tools'

export interface ToolCallMessage {
  tool_name: string
  tool_arguments: Array<{
    argument_name: string
    argument: string
  }>
  status: 'pending' | 'approved' | 'rejected'
  pending_reason: string
  tool_response: string
}

export interface Message {
  role: MsgRole;
  content: string
  attachments?: Array<{
    attachment_id: string
    attachment_name: string
  }>
  thought: string
}

export interface SseHistoryData {
  message_id: string;
  type: MsgRole;
  created_at: string;
  finished_at: string;
  data: ToolCallMessage | Message;
}

export interface SseHistoryResponse {
  history_messages: SseHistoryData[];
}

export interface SseMessageDeltaData {
  message_id: string;
  delta: string;
  is_thinking?: boolean;
}

export interface SseMetaData {
  message_id: string;
  metadata: Record<string, any>;
}

export interface SseToolCallData extends ToolCallMessage {
  message_id: string;
}

export interface SseErrorData {
  error_message: string;
}

export interface SseDoneData {
}

export interface SseKeepAliveData {
}
// events

