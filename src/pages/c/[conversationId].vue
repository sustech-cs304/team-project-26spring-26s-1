<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0">

        <!-- 消息列表 -->
        <v-sheet ref="scrollEl" color="transparent" class="flex-grow-1 overflow-y-auto">
            <v-container max-width="800" class="px-6 py-4">
                <template v-for="(msg, i) in messages" :key="`${i}-${msg.role}`">

                    <!-- 用户消息 -->
                    <v-row v-if="msg.role === 'user'" justify="end" class="mb-1" density="compact">
                        <v-col :cols="editingIndex === i ? undefined : 'auto'" class="d-flex align-end ga-2"
                            style="max-width: 83%;">
                            <!-- 编辑模式 -->
                            <v-sheet v-if="editingIndex === i" class="flex-grow-1" color="transparent">
                                <v-textarea v-model="editingContent" variant="solo" rounded="lg" rows="1" auto-grow
                                    max-rows="8" hide-details autofocus @keydown.enter.exact.prevent="submitEdit(i)"
                                    @keydown.esc="cancelEdit" :color="cardColor" />
                                <div class="d-flex justify-end ga-1 mt-1">
                                    <v-btn size="small" variant="text" @click="cancelEdit" rounded="lg">取消</v-btn>
                                    <v-btn size="small" variant="flat" rounded="lg" color="surface-variant"
                                        :disabled="!editingContent.trim() || loading" @click="submitEdit(i)">发送</v-btn>
                                </div>
                            </v-sheet>
                            <!-- 展示模式 -->
                            <v-sheet v-else rounded="lg" class="px-3 py-2" style="cursor: pointer;" :color="cardColor"
                                @click="startEdit(i, msg.content)">
                                <MarkdownRenderer :content="msg.content" />
                            </v-sheet>
                            <v-avatar size="30" class="flex-shrink-0">
                                <v-icon size="16">mdi-account</v-icon>
                            </v-avatar>
                        </v-col>
                    </v-row>

                    <!-- Tool 消息（HumanInLoop 审批卡片） -->
                    <v-row v-else-if="msg.role === 'tools'" justify="start" class="mb-1" density="compact">
                        <v-col class="pa-0" style="min-width: 0; max-width: 100%;">
                            <HumanInLoopCard v-if="msg.toolCall && msg.toolCall.status === 'pending'"
                                :tool="msg.toolCall"
                                @action="(action) => handleToolAction(msg.toolCall!, msg.message_id!, action)" />
                        </v-col>
                    </v-row>

                    <!-- AI 消息 -->
                    <template v-else-if="msg.role === 'assistant'">
                        <v-row class="mb-1 ma-0" density="compact">
                            <v-col class="pa-0" style="min-width: 0; max-width: 100%;">

                                <div class="assistant-turn">
                                    <!-- Thinking 展示 -->
                                    <ThinkingMsg v-if="msg.thinking" :content="msg.thinking"
                                        :is-active="msg.thinkingActive" />

                                    <!-- 已完成的 tool calls 展示 -->
                                    <ToolCallGroup v-if="msg.toolCalls && msg.toolCalls.length > 0"
                                        :steps="msg.toolCalls" :auto-collapse="!!msg.content" />

                                    <!-- 文本内容 -->
                                    <v-sheet v-if="msg.content" rounded="lg" color="transparent" class="px-0 py-1 pl-3">
                                        <MarkdownRenderer :content="msg.content" />
                                    </v-sheet>
                                </div>

                                <!-- 操作栏 -->
                                <v-row v-if="msg.content" align="center" class="ml-2 ga-0" style="opacity: 0.6;">
                                    <v-tooltip text="重试" location="bottom">
                                        <template v-slot:activator="{ props }">
                                            <v-btn v-bind="props" icon="mdi-reload" size="x-small" variant="text"
                                                active-color="primary" @click="retryMessage(i)" :disabled="loading" />
                                        </template>
                                    </v-tooltip>
                                    <v-tooltip text="Copy" location="bottom">
                                        <template v-slot:activator="{ props }">
                                            <v-btn v-bind="props" icon="mdi-content-copy" size="x-small" variant="text"
                                                @click="copyText(msg.content)" />
                                        </template>
                                    </v-tooltip>
                                    <TypingIndicator v-if="loading && i === messages.length - 1" />
                                </v-row>
                            </v-col>
                        </v-row>
                    </template>

                </template>
            </v-container>
        </v-sheet>

        <!-- 底部输入区 -->
        <v-sheet elevation="0" color="transparent">
            <v-container max-width="800" class="px-6 pb-5 pt-2">
                <MessageInput ref="messageInputRef" v-model="input" :loading="loading" :disabled="hasPendingTool"
                    @send="send" @stop="stop" />
            </v-container>
        </v-sheet>
    </v-container>
</template>


<script setup lang="ts">
    import MessageInput from '@/components/chat/MessageInput.vue'
    import TypingIndicator from '@/components/chat/TypingIndicator.vue'
    import ThinkingMsg from '@/components/chat/ThinkingMsg.vue'
    import ToolCallGroup from '@/components/chat/ToolCallGroup.vue'
    import HumanInLoopCard from '@/components/chat/HumanInLoopCard.vue'
    import MarkdownRenderer from '@/components/chat/MarkdownRenderer.vue'
    import type { ToolCallMessage, MsgRole } from '@/types/conversation'
    import type {
        SseHistoryData,
        SseHistoryResponse,
        SseMessageDeltaData,
        SseToolCallData,
        SseMetaData,
        SseDoneData,
        SseErrorData,
        SseHandlers,
        Message,
    } from '@/types/conversation'
    import { chatCompletion, cancelChat, generateUUID } from '@/api/conversation'
    import { pendingPrompt } from '@/utils/pendingPrompt'
    import { useAppStore } from '@/stores/app'
    import { copyText } from '@/utils/copyText'
    import { useTheme } from 'vuetify'

    // ── 内部扩展的 ChatMessage 类型 ──
    interface ChatMessage {
        role: MsgRole
        content: string
        message_id?: string
        created_at?: number
        thinking?: string
        thinkingActive?: boolean
        toolCall?: ToolCallMessage        // 用于 role='tools' 的 HumanInLoop 卡片
        toolCalls?: ToolCallMessage[]      // 用于 assistant 消息中已完成的 tool calls
    }

    const route = useRoute()
    const conversationId = computed(() => route.params.conversationId as string)
    const appStore = useAppStore()

    interface SendChatRequestOptions {
        content: string
        messageId?: string
        addUserMessage?: boolean
        clearFromIndex?: number
    }

    const scrollEl = ref<InstanceType<typeof import('vuetify/components').VSheet> | null>(null)
    const messageInputRef = ref<InstanceType<typeof MessageInput> | null>(null)
    const input = ref('')
    const loading = ref(false)

    // ── 向布局层注册 MessageInput（用于拖拽上传） ──
    const registerMessageInput = inject<(ref: any) => void>('registerMessageInput')
    const unregisterMessageInput = inject<() => void>('unregisterMessageInput')

    onMounted(() => {
        registerMessageInput?.(messageInputRef.value)
        loadConversation()
    })

    onBeforeUnmount(() => {
        unregisterMessageInput?.()
    })

    watch(messageInputRef, (ref) => {
        if (ref) registerMessageInput?.(ref)
    })

    const messages = reactive<ChatMessage[]>([])

    const hasPendingTool = computed(() =>
        messages.some(m => m.role === 'tools' && m.toolCall?.status === 'pending')
    )

    // ── 用户消息编辑 ──
    const theme = useTheme()
    const cardColor = computed(() => theme.current.value.dark ? 'grey-darken-3' : 'grey-lighten-3')

    const editingIndex = ref<number | null>(null)
    const editingContent = ref('')

    const startEdit = (index: number, content: string) => {
        if (loading.value || hasPendingTool.value) return
        editingIndex.value = index
        editingContent.value = content
    }

    const cancelEdit = () => {
        editingIndex.value = null
        editingContent.value = ''
    }

    const submitEdit = async (userMsgIndex: number) => {
        const newContent = editingContent.value.trim()
        if (!newContent || loading.value) return

        cancelEdit()

        // 清除该用户消息及之后的所有内容，用编辑后的内容重新发送
        // clearFromIndex 从用户消息开始清除，addUserMessage: true 会重新添加用户消息
        await sendChatRequest({
            content: newContent,
            messageId: messages[userMsgIndex]?.message_id,
            addUserMessage: true,
            clearFromIndex: userMsgIndex,
        })
    }

    const scrollToBottom = async () => {
        await nextTick()
        const el = scrollEl.value?.$el as HTMLElement | undefined
        if (el) el.scrollTop = el.scrollHeight
    }

    const scrollIfAtBottom = async () => {
        await nextTick()
        const el = scrollEl.value?.$el as HTMLElement | undefined
        if (!el) return
        const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
        if (distanceFromBottom <= 150) el.scrollTop = el.scrollHeight
    }

    let currentAbortCtrl: AbortController | null = null
    let currentMessageId: string | null = null

    // ── 历史消息转换 ──

    /** 将后端历史消息转换为 ChatMessage */
    const historyToMessage = (m: SseHistoryData): ChatMessage => {
        const base: ChatMessage = {
            role: m.type,
            content: '',
            message_id: m.message_id,
            created_at: Number(m.created_at) || Date.now(),
        }

        if (m.type === 'tools') {
            // tool 消息：data 是 ToolCallMessage
            const toolData = m.data as ToolCallMessage
            base.toolCall = toolData
            return base
        }

        // user / assistant 消息：data 是 Message
        const msgData = m.data as Message
        base.content = msgData.content || ''

        if (m.type === 'assistant' && msgData.thought) {
            base.thinking = msgData.thought
            base.thinkingActive = false
        }

        return base
    }

    // ── SSE 回调处理器 ──

    /** 创建统一的 SSE 回调处理器 */
    const createSseHandlers = (assistantMsg: ChatMessage): SseHandlers => ({

        onDelta: (data: SseMessageDeltaData) => {
            if (data.message_id) currentMessageId = data.message_id

            if (data.is_thinking) {
                // 追加到 thinking 字段
                assistantMsg.thinking = (assistantMsg.thinking || '') + data.delta
                assistantMsg.thinkingActive = true
            } else {
                // 关闭 thinking 活跃状态
                if (assistantMsg.thinkingActive) {
                    assistantMsg.thinkingActive = false
                }
                // 追加到 content
                assistantMsg.content += data.delta
            }
            void scrollIfAtBottom()
        },

        onToolCall: (data: SseToolCallData) => {
            if (data.message_id) currentMessageId = data.message_id

            const toolMsg: ToolCallMessage = {
                tool_name: data.tool_name,
                tool_arguments: data.tool_arguments,
                status: data.status,
                pending_reason: data.pending_reason,
                tool_response: data.tool_response,
            }

            if (data.status === 'pending') {
                messages.push({
                    role: 'tools',
                    content: '',
                    created_at: Date.now(),
                    message_id: data.message_id,
                    toolCall: toolMsg,
                })
            } else {
                if (!assistantMsg.toolCalls) assistantMsg.toolCalls = []
                assistantMsg.toolCalls.push(toolMsg)
            }
            void scrollToBottom()
        },

        onMetaData: (data: SseMetaData) => {
            if (data.message_id) currentMessageId = data.message_id
            const metadata = data.metadata
            if (metadata?.title && metadata?.conversation_id) {
                appStore.setConversationTitle(metadata.conversation_id, metadata.title)
            }
        },

        onDone: (_data: SseDoneData) => {
            assistantMsg.thinkingActive = false
            assistantMsg.created_at = Date.now()
            loading.value = false
            currentAbortCtrl = null
            currentMessageId = null
        },

        onError: (data: SseErrorData) => {
            assistantMsg.thinkingActive = false
            assistantMsg.content += `\n[错误] ${data.error_message}`
            assistantMsg.created_at = Date.now()
            loading.value = false
            currentAbortCtrl = null
            currentMessageId = null
        },

        onFetchError: (err: unknown) => {
            console.error('[SSE] fetch error:', err)
            assistantMsg.thinkingActive = false
            assistantMsg.content += '\n[网络错误，请重试]'
            assistantMsg.created_at = Date.now()
            loading.value = false
            currentAbortCtrl = null
            currentMessageId = null
        },
    })

    /** 统一的消息发送函数 */
    const sendChatRequest = async (options: SendChatRequestOptions) => {
        stop()

        if (options.clearFromIndex !== undefined) {
            messages.splice(options.clearFromIndex, messages.length - options.clearFromIndex)
        }

        if (options.addUserMessage !== false) {
            messages.push({ role: 'user', content: options.content, created_at: Date.now() })
            await scrollToBottom()
        }

        loading.value = true

        // 预先创建 assistant 消息占位
        const assistantMsg: ChatMessage = reactive({
            role: 'assistant' as const,
            content: '',
            created_at: Date.now(),
        })
        messages.push(assistantMsg)

        await scrollToBottom()

        const requestId = generateUUID()

        currentAbortCtrl = chatCompletion(
            {
                conversation_id: conversationId.value,
                request_id: requestId,
                content: options.content,
                create_at: Date.now(),
                need_history: false,
                message_id: options.messageId,
            },
            createSseHandlers(assistantMsg)
        )
    }

    const processMessage = async (text: string) => {
        await sendChatRequest({
            content: text,
            addUserMessage: true,
        })
    }

    /** 加载对话（首次进入或切换 conversationId 时） */
    const loadConversation = async () => {
        currentAbortCtrl?.abort()
        currentAbortCtrl = null
        currentMessageId = null
        messages.splice(0)
        loading.value = false

        const prompt = pendingPrompt.value
        if (prompt) {
            pendingPrompt.value = null
            await processMessage(prompt)
        } else {
            loading.value = true
            currentAbortCtrl = chatCompletion(
                {
                    conversation_id: conversationId.value,
                    request_id: generateUUID(),
                    create_at: Date.now(),
                    need_history: true,
                },
                {
                    onHistory: (data: SseHistoryResponse) => {
                        if (!data.history_messages) { loading.value = false; return }
                        messages.splice(0, messages.length, ...data.history_messages.map(historyToMessage))
                        loading.value = false
                        void scrollToBottom()
                    },
                    onDone: () => { loading.value = false },
                    onError: () => { loading.value = false },
                    onFetchError: () => { loading.value = false },
                }
            )
        }
    }

    watch(conversationId, () => {
        loadConversation()
    })

    /** 处理 Tool 用户操作（approve/skip/reject） */
    const handleToolAction = async (tool: ToolCallMessage, _messageId: string | undefined, action: 'approve' | 'skip' | 'reject') => {
        tool.status = action === 'approve' ? 'approved' : 'rejected'
        await processMessage(action)
    }

    const send = async () => {
        const text = input.value.trim()
        if (!text || loading.value) return
        input.value = ''
        await processMessage(text)
    }

    const stop = () => {
        if (currentMessageId) {
            cancelChat(conversationId.value, currentMessageId).catch(() => { })
        }
        currentAbortCtrl?.abort()
        currentAbortCtrl = null
        currentMessageId = null
        loading.value = false
        const last = messages[messages.length - 1]
        if (last?.role === 'assistant') {
            last.thinkingActive = false
            if (!last.created_at) last.created_at = Date.now()
        }
    }

    /** 重试消息 */
    const retryMessage = async (messageIndex: number) => {
        const agentMsg = messages[messageIndex]
        if (agentMsg?.role !== 'assistant' || loading.value) return

        const userMsgIndex = messageIndex - 1
        const userMsg = messages[userMsgIndex]
        if (!userMsg || userMsg.role !== 'user') return

        await sendChatRequest({
            content: userMsg.content,
            messageId: userMsg.message_id,
            addUserMessage: false,
            clearFromIndex: messageIndex,
        })
    }
</script>
