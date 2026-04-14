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

export type SseEventTypes = 'history' | 'user_message' | 'delta' | 'metadata' | 'tool_call' | 'error' | 'done' | 'keep_alive'

export type MsgRole = 'user' | 'assistant' | 'system' | 'tools'
export type HistoryMessageRole = Exclude<MsgRole, 'tools'>

export interface ToolArgument {
  argument_name: string
  argument: string
}

export interface ToolCallMessage {
  tool_name: string
  tool_arguments: ToolArgument[]
  status: 'pending' | 'approved' | 'rejected' | 'running' | string
  pending_reason?: string
  tool_response?: string
}

export type QuizType = 'single' | 'multiple'

export interface QuizCardData {
  quiz_id?: string
  title: string
  description?: string
  type: QuizType
  choices: string[]
  correct_choice_indexes: number[]
  explanation: string
}

export interface QuizToolCard {
  card_id: string
  quizzes: QuizCardData[]
}

interface QuizQuestionRaw {
  title: string
  type: QuizType
  choices: string[]
  correct_choice_indexes: number[]
  explanation: string
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

const isQuizQuestionRaw = (value: unknown): value is QuizQuestionRaw => {
  if (!value || typeof value !== 'object') return false

  const question = value as QuizQuestionRaw
  return typeof question.title === 'string'
    && (question.type === 'single' || question.type === 'multiple')
    && Array.isArray(question.choices)
    && Array.isArray(question.correct_choice_indexes)
    && typeof question.explanation === 'string'
}

const parseQuizQuestionsArgument = (raw: string): unknown => {
  let index = 0

  const isWhitespace = (char: string | undefined) => char === ' ' || char === '\n' || char === '\r' || char === '\t'

  const skipWhitespace = () => {
    while (isWhitespace(raw[index])) index += 1
  }

  const parseString = (): string => {
    const quote = raw[index]
    if (quote !== '\'' && quote !== '"') {
      throw new Error('Expected string')
    }

    index += 1
    let result = ''

    while (index < raw.length) {
      const char = raw[index]

      if (char === '\\') {
        const next = raw[index + 1]
        if (next === undefined) throw new Error('Invalid escape sequence')

        if (next === 'u') {
          const code = raw.slice(index + 2, index + 6)
          if (code.length !== 4 || /[^0-9a-fA-F]/.test(code)) throw new Error('Invalid unicode escape')
          result += String.fromCharCode(parseInt(code, 16))
          index += 6
          continue
        }

        const escapedMap: Record<string, string> = {
          '\'': '\'',
          '"': '"',
          '\\': '\\',
          '/': '/',
          b: '\b',
          f: '\f',
          n: '\n',
          r: '\r',
          t: '\t',
        }

        result += escapedMap[next] ?? next
        index += 2
        continue
      }

      if (char === quote) {
        index += 1
        return result
      }

      result += char
      index += 1
    }

    throw new Error('Unterminated string')
  }

  const parseNumber = (): number => {
    const start = index
    if (raw[index] === '-') index += 1

    while (/[0-9]/.test(raw[index] ?? '')) index += 1

    if (raw[index] === '.') {
      index += 1
      while (/[0-9]/.test(raw[index] ?? '')) index += 1
    }

    const numberText = raw.slice(start, index)
    const number = Number(numberText)
    if (Number.isNaN(number)) throw new Error('Invalid number')
    return number
  }

  const parseLiteral = (literal: string, value: unknown): unknown => {
    if (raw.slice(index, index + literal.length) !== literal) {
      throw new Error(`Expected ${literal}`)
    }
    index += literal.length
    return value
  }

  const parseArray = (): unknown[] => {
    index += 1
    const result: unknown[] = []
    skipWhitespace()

    if (raw[index] === ']') {
      index += 1
      return result
    }

    while (index < raw.length) {
      result.push(parseValue())
      skipWhitespace()

      if (raw[index] === ',') {
        index += 1
        skipWhitespace()
        continue
      }

      if (raw[index] === ']') {
        index += 1
        return result
      }

      throw new Error('Expected , or ]')
    }

    throw new Error('Unterminated array')
  }

  const parseObject = (): Record<string, unknown> => {
    index += 1
    const result: Record<string, unknown> = {}
    skipWhitespace()

    if (raw[index] === '}') {
      index += 1
      return result
    }

    while (index < raw.length) {
      skipWhitespace()
      const key = parseString()
      skipWhitespace()

      if (raw[index] !== ':') {
        throw new Error('Expected :')
      }

      index += 1
      skipWhitespace()
      result[key] = parseValue()
      skipWhitespace()

      if (raw[index] === ',') {
        index += 1
        skipWhitespace()
        continue
      }

      if (raw[index] === '}') {
        index += 1
        return result
      }

      throw new Error('Expected , or }')
    }

    throw new Error('Unterminated object')
  }

  const parseValue = (): unknown => {
    skipWhitespace()
    const char = raw[index]

    if (char === '[') return parseArray()
    if (char === '{') return parseObject()
    if (char === '\'' || char === '"') return parseString()
    if (char === '-' || /[0-9]/.test(char ?? '')) return parseNumber()
    if (char === 't') return parseLiteral('true', true)
    if (char === 'f') return parseLiteral('false', false)
    if (char === 'n') return parseLiteral('null', null)

    throw new Error(`Unexpected token ${char ?? 'EOF'}`)
  }

  const value = parseValue()
  skipWhitespace()

  if (index !== raw.length) {
    throw new Error('Unexpected trailing content')
  }

  return value
}

export const extractQuizCardsFromToolCall = (tool?: ToolCallMessage | null): QuizToolCard[] => {
  if (!isQuizCardToolMessage(tool)) return []

  return tool.tool_arguments.flatMap((item) => {
    if (item.argument_name !== 'questions') return []

    let questions: unknown
    try {
      questions = parseQuizQuestionsArgument(item.argument)
    } catch {
      return []
    }

    if (!Array.isArray(questions)) return []

    const quizzes = questions
      .filter(isQuizQuestionRaw)
      .map((question, index) => ({
        quiz_id: `quiz_${index + 1}`,
        title: question.title,
        type: question.type,
        choices: question.choices,
        correct_choice_indexes: question.correct_choice_indexes
          .filter(choiceIndex => Number.isInteger(choiceIndex) && choiceIndex >= 0 && choiceIndex < question.choices.length),
        explanation: question.explanation,
      }))

    if (quizzes.length === 0) return []

    return [{
      card_id: `${tool.tool_name}_${item.argument_name}`,
      quizzes,
    }]
  })
}

export interface Message {
  role: HistoryMessageRole;
  content: string
  attachments?: MessageAttachmentPayload[]
  thought?: string
}

export type MessageAttachmentPayload = MessageAttachmentReference | string

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
  message_id?: string;
  title?: string;
  metadata?: Record<string, any>;
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

