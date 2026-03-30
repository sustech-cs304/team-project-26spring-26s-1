<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0">

        <!-- 消息列表 -->
        <v-sheet ref="scrollEl" color="transparent" class="flex-grow-1 overflow-y-auto">
            <v-container max-width="800" class="px-6 py-4">
                <template v-for="(msg, i) in messages" :key="msg.message_id || `${i}-${msg.role}`">

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

                    <!-- Tool 消息（独立节点：pending 显示审批卡片，非 pending 显示 ToolCallGroup） -->
                    <v-row v-else-if="msg.role === 'tools' && msg.toolCall" justify="start" class="mb-1"
                        density="compact">
                        <v-col class="pa-0" style="min-width: 0; max-width: 100%;">
                            <HumanInLoopCard v-if="msg.toolCall.status === 'pending'" :tool="msg.toolCall"
                                @action="(action) => handleToolAction(msg.toolCall!, msg.message_id!, action)" />
                            <ToolCallGroup v-else :steps="[msg.toolCall]" :auto-collapse="false" />
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

                                    <!-- 文本内容 -->
                                    <v-sheet v-if="msg.content" rounded="lg" color="transparent" class="px-0 pt-4 pl-2">
                                        <MarkdownRenderer :content="msg.content" />
                                    </v-sheet>
                                </div>

                            </v-col>
                        </v-row>
                    </template>

                    <v-row v-if="shouldShowTurnActions(i)" align="center" class="ma-0 ga-0" style="opacity: 0.6;">
                        <v-tooltip text="重试" location="bottom">
                            <template v-slot:activator="{ props }">
                                <v-btn v-bind="props" icon="mdi-reload" size="x-small" variant="text"
                                    active-color="primary" @click="retryTurn(i)" :disabled="loading" />
                            </template>
                        </v-tooltip>
                        <v-tooltip text="Copy" location="bottom">
                            <template v-slot:activator="{ props }">
                                <v-btn v-bind="props" icon="mdi-content-copy" size="x-small" variant="text"
                                    @click="copyTurnAssistantContent(i)" />
                            </template>
                        </v-tooltip>
                        <TypingIndicator v-if="loading && i === messages.length - 1" />
                    </v-row>

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
        SseHistoryMessageData,
        SseHistoryToolData,
        SseMessageDeltaData,
        SseToolCallData,
        SseMetaData,
        SseDoneData,
        SseErrorData,
        SseHandlers,
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
        toolCall?: ToolCallMessage
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
    const messageMap = new Map<string, ChatMessage>()

    /** 根据 message_id 查找或创建消息节点 */
    const getOrCreateMessage = (messageId: string, role: MsgRole): ChatMessage => {
        const existing = messageMap.get(messageId)
        if (existing) return existing

        const msg: ChatMessage = reactive({
            role,
            content: '',
            message_id: messageId,
            created_at: Date.now(),
        })
        messages.push(msg)
        messageMap.set(messageId, msg)
        return msg
    }

    const hasPendingTool = computed(() =>
        messages.some(m => m.role === 'tools' && m.toolCall?.status === 'pending')
    )

    interface TurnInfo {
        start: number
        end: number
        hasAssistantContent: boolean
        assistantCombinedContent: string
        userMsg?: ChatMessage
    }

    const getTurnInfo = (index: number): TurnInfo | null => {
        if (!messages.length) return null
        const i = Math.max(0, Math.min(index, messages.length - 1))
        let start = 0
        for (let cursor = i; cursor >= 0; cursor--) {
            if (messages[cursor]?.role === 'user') {
                start = cursor
                break
            }
        }
        let end = messages.length - 1
        for (let cursor = start + 1; cursor < messages.length; cursor++) {
            if (messages[cursor]?.role === 'user') {
                end = cursor - 1
                break
            }
        }
        const chunks: string[] = []
        for (let cursor = start; cursor <= end; cursor++) {
            const msg = messages[cursor]
            if (msg?.role === 'assistant' && msg.content.trim()) {
                chunks.push(msg.content.trim())
            }
        }
        const userMsg = messages[start]?.role === 'user' ? messages[start] : undefined
        return {
            start,
            end,
            hasAssistantContent: chunks.length > 0,
            assistantCombinedContent: chunks.join('\n\n'),
            userMsg,
        }
    }

    /** 轮级操作栏可见性。 */
    const shouldShowTurnActions = (index: number): boolean => {
        const info = getTurnInfo(index)
        return !!info && info.end === index && info.hasAssistantContent
    }

    const copyTurnAssistantContent = (index: number) => {
        const info = getTurnInfo(index)
        if (!info?.assistantCombinedContent) return
        void copyText(info.assistantCombinedContent)
    }

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
        const historyData = m.data
        const base: ChatMessage = {
            role: historyData.type === 'tool' ? 'tools' : historyData.role,
            content: '',
            message_id: m.message_id,
            created_at: Number(m.created_at) || Date.now(),
        }

        if (historyData.type === 'tool') {
            const toolData = historyData as SseHistoryToolData
            base.toolCall = toolData
            return base
        }

        const msgData = historyData as SseHistoryMessageData
        base.content = msgData.content || ''

        if (msgData.role === 'assistant' && msgData.thought) {
            base.thinking = msgData.thought
            base.thinkingActive = false
        }

        return base
    }

    /** 将消息数组同步到 messageMap */
    const syncMessageMap = () => {
        messageMap.clear()
        for (const msg of messages) {
            if (msg.message_id) messageMap.set(msg.message_id, msg)
        }
    }

    // ── SSE 回调处理器 ──

    /** 获取最后一个 assistant 消息（用于 done/error 等无 message_id 的事件） */
    const getLastAssistantMsg = (): ChatMessage | undefined => {
        for (let i = messages.length - 1; i >= 0; i--) {
            if (messages[i]?.role === 'assistant') return messages[i]
        }
        return undefined
    }

    /** 创建统一的 SSE 回调处理器（不再绑定单一 assistantMsg） */
    const createSseHandlers = (): SseHandlers => ({

        onDelta: (data: SseMessageDeltaData) => {
            if (data.message_id) currentMessageId = data.message_id

            // 根据 message_id 查找或创建 assistant 消息节点
            const msg = getOrCreateMessage(data.message_id, 'assistant')

            if (data.is_thinking) {
                msg.thinking = (msg.thinking || '') + data.delta
                msg.thinkingActive = true
            } else {
                if (msg.thinkingActive) {
                    msg.thinkingActive = false
                }
                msg.content += data.delta
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

            // tool_call 始终作为独立的 tools 节点
            const msg = getOrCreateMessage(data.message_id, 'tools')
            msg.toolCall = toolMsg
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
            for (const msg of messages) {
                if (msg.role === 'assistant' && msg.thinking) {
                    msg.thinkingActive = false
                }
            }
            const last = getLastAssistantMsg()
            if (last) {
                last.created_at = Date.now()
            }
            loading.value = false
            currentAbortCtrl = null
            currentMessageId = null
        },

        onError: (data: SseErrorData) => {
            const last = getLastAssistantMsg()
            if (last) {
                last.thinkingActive = false
                if (last.content) {
                    last.content += `\n[错误] ${data.error_message}`
                } else {
                    last.content = `[错误] ${data.error_message}`
                }
                last.created_at = Date.now()
            }
            loading.value = false
            currentAbortCtrl = null
            currentMessageId = null
        },

        onFetchError: (err: unknown) => {
            console.error('[SSE] fetch error:', err)
            const last = getLastAssistantMsg()
            if (last) {
                last.thinkingActive = false
                if (last.content) {
                    last.content += '\n[网络错误，请重试]'
                } else {
                    last.content = '[网络错误，请重试]'
                }
                last.created_at = Date.now()
            }
            loading.value = false
            currentAbortCtrl = null
            currentMessageId = null
        },
    })

    const createHistoryResumeHandlers = (): SseHandlers => {
        const baseHandlers = createSseHandlers()

        return {
            ...baseHandlers,
            onHistory: (data: SseHistoryData) => {
                if (!data?.message_id || messageMap.has(data.message_id)) {
                    return
                }
                const msg = historyToMessage(data)
                messages.push(msg)
                messageMap.set(data.message_id, msg)
                void scrollToBottom()
            },
            onDone: (data: SseDoneData) => {
                baseHandlers.onDone?.(data)
            },
            onError: (data: SseErrorData) => {
                baseHandlers.onError?.(data)
            },
            onFetchError: (err: unknown) => {
                baseHandlers.onFetchError?.(err)
            },
        }
    }

    /** 统一的消息发送函数 */
    const sendChatRequest = async (options: SendChatRequestOptions) => {
        stop()

        if (options.clearFromIndex !== undefined) {
            // 清除被删消息在 messageMap 中的引用
            for (let i = options.clearFromIndex; i < messages.length; i++) {
                const mid = messages[i]?.message_id
                if (mid) messageMap.delete(mid)
            }
            messages.splice(options.clearFromIndex, messages.length - options.clearFromIndex)
        }

        if (options.addUserMessage !== false) {
            messages.push({ role: 'user', content: options.content, created_at: Date.now() })
            await scrollToBottom()
        }

        loading.value = true
        await scrollToBottom()

        const requestId = generateUUID()

        currentAbortCtrl = chatCompletion(
            {
                conversation_id: conversationId.value,
                request_id: requestId,
                content: options.content,
                created_at: Date.now(),
                need_history: false,
                message_id: options.messageId,
            },
            createSseHandlers()
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
        messageMap.clear()
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
                    created_at: Date.now(),
                    need_history: true,
                },
                createHistoryResumeHandlers()
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
        const last = getLastAssistantMsg()
        if (last) {
            last.thinkingActive = false
            if (!last.created_at) last.created_at = Date.now()
        }
    }

    /** 按轮重试：定位该轮 user 消息，重发并清理该轮末尾之后内容。 */
    const retryTurn = async (messageIndex: number) => {
        if (loading.value || !messages.length) return
        const info = getTurnInfo(messageIndex)
        if (!info?.userMsg) return

        await sendChatRequest({
            content: info.userMsg.content,
            messageId: info.userMsg.message_id,
            addUserMessage: false,
            clearFromIndex: info.start + 1,
        })
    }
</script>
