export interface Conversation {
  conversation_id: string;
  created_at: number;
  updated_at: number;
  title: string;
  is_active: boolean;
  is_pinned: boolean;
}

export interface CreateConversationResponse {
  conversation_id: string;
  created_at: number;
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
  event: SseEventTypes;
  data: T;
}

export interface SseHandlers {
  onHistory?: (data: SseHistoryData) => void;
  onUserMessage?: (data: SseUserMessageData) => void;
  onDelta?: (data: SseMessageDeltaData) => void;
  onMetaData?: (data: SseMetaData) => void;
  onToolCall?: (data: SseToolCallData) => void;
  onError?: (data: SseErrorData) => void;
  onKeepAlive?: (data: SseKeepAliveData) => void;
  onDone?: (data: SseDoneData) => void;
  onFetchError?: (error: any) => void;
}

export type SseEventTypes = 'history' | 'user_message' | 'delta' | 'meta_data' | 'tool_call' | 'error' | 'done' | 'keep_alive'

export type MsgRole = 'user' | 'assistant' | 'system' | 'tools'
export type HistoryMessageRole = Exclude<MsgRole, 'tools'>

export interface ToolArgument {
  argument_name: string
  argument: string
}

export interface ToolCallMessage {
  tool_name: string
  tool_arguments: ToolArgument[]
  status: 'pending' | 'approved' | 'rejected'
  pending_reason?: string
  tool_response?: string
}

export type QuizType = 'single' | 'multiple'

export interface QuizOption {
  id: string
  content: string
}

export interface QuizCardData {
  quiz_id?: string
  title: string
  description?: string
  type: QuizType
  options: QuizOption[]
  answers: string[]
  explanation: string
}

export interface QuizCardPayload {
  quizzes: QuizCardData[]
}

export interface QuizToolCard extends QuizCardPayload {
  card_id: string
}

export interface QuizCardToolArgument extends ToolArgument {
  argument_name: string
  argument: string
}

export interface QuizCardToolMessage extends Omit<ToolCallMessage, 'tool_name' | 'tool_arguments'> {
  tool_name: 'quiz_card'
  tool_arguments: QuizCardToolArgument[]
}

export const isQuizCardToolMessage = (tool?: ToolCallMessage | null): tool is QuizCardToolMessage =>
  tool?.tool_name === 'quiz_card'

const isQuizCardPayload = (value: unknown): value is QuizCardPayload => {
  if (!value || typeof value !== 'object') return false
  return Array.isArray((value as QuizCardPayload).quizzes)
}

export const parseQuizCardPayload = (raw: string): QuizCardPayload | null => {
  try {
    const parsed = JSON.parse(raw) as unknown
    return isQuizCardPayload(parsed) ? parsed : null
  } catch {
    return null
  }
}

export const extractQuizCardsFromToolCall = (tool?: ToolCallMessage | null): QuizToolCard[] => {
  if (!isQuizCardToolMessage(tool)) return []

  return tool.tool_arguments.flatMap((item) => {
    const payload = parseQuizCardPayload(item.argument)
    if (!payload) return []

    return [{
      card_id: item.argument_name,
      quizzes: payload.quizzes,
    }]
  })
}

export interface Message {
  role: HistoryMessageRole;
  content: string
  attachments?: MessageAttachmentReference[]
  thought?: string
}

export interface MessageAttachmentReference {
  file_id?: string
  attachment_id?: string
  attachment_name?: string
}

export interface SseHistoryToolData extends ToolCallMessage {
  type: 'tool'
}

export interface SseHistoryMessageData extends Message {
  type: 'message'
}

export interface SseHistoryData {
  message_id: string;
  created_at: string;
  finished_at: string;
  data: SseHistoryToolData | SseHistoryMessageData;
}

export interface SseUserMessageData {
  message_id: string;
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

