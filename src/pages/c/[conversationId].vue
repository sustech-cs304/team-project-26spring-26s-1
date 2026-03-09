<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0">

        <!-- 消息列表 -->
        <v-sheet ref="scrollEl" color="transparent" class="flex-grow-1 overflow-y-auto">
            <v-container max-width="800" class="px-6 py-4">
                <template v-for="(msg, i) in messages" :key="`${i}-${msg.role}`">

                    <!-- 用户消息 -->
                    <v-row v-if="msg.role === 'user'" justify="end" class="mb-1" density="compact">
                        <v-col cols="auto" class="d-flex align-end ga-2" style="max-width: 83%;">
                            <v-sheet rounded="lg" color="" class="px-3 py-2">
                                <MarkdownRenderer :content="msg.content" />
                            </v-sheet>
                            <v-avatar size="30" class="flex-shrink-0">
                                <v-icon size="16">mdi-account</v-icon>
                            </v-avatar>
                        </v-col>
                    </v-row>

                    <template v-else-if="msg.role === 'assistant'">
                        <!-- 思维链独立行：与消息气泡分离，确保组件挂载时 isActive 已就位 -->
                        <v-row v-if="msg.thinkingSteps && msg.thinkingSteps.length > 0" class="mb-0" density="compact">
                            <v-col class="pa-0" style="min-width: 0; max-width: 100%;">
                                <ThinkingChain :key="`thinking-${i}`" :steps="msg.thinkingSteps"
                                    :is-active="msg.thinkingActive" />
                            </v-col>
                        </v-row>

                        <!-- AI 消息气泡行：content 为空时（流式初始阶段）也保留节点，避免 delta 写入后才挂载 -->
                        <v-row v-show="msg.content" class="mb-1 ma-0" density="compact">
                            <v-col class="pa-0" style="min-width: 0; max-width: 100%;">
                                <v-sheet rounded="lg" color="transparent" class="px-0 py-1 pl-3">
                                    <MarkdownRenderer :content="msg.content" />
                                </v-sheet>
                                <v-row align="center" class="ml-2 ga-0" style="opacity: 0.6;">
                                    <span class="text-body-small">{{ msg.time }}</span>
                                    <v-tooltip text="Reload" location="bottom">
                                        <template v-slot:activator="{ props }">
                                            <v-btn v-bind="props" icon="mdi-reload" size="x-small" variant="text"
                                                active-color="primary" />
                                        </template>
                                    </v-tooltip>
                                    <v-tooltip text="Copy" location="bottom">
                                        <template v-slot:activator="{ props }">
                                            <v-btn v-bind="props" icon="mdi-content-copy" size="x-small" variant="text"
                                                @click="copy(msg.content)" />
                                        </template>
                                    </v-tooltip>
                                </v-row>
                            </v-col>
                        </v-row>
                    </template>

                </template>

                <!-- 加载中：仅当无活跃思维链时显示，避免与思维链卡片重叠 -->
                <TypingIndicator v-if="loading && !hasActiveThinking" />
            </v-container>
        </v-sheet>

        <!-- 底部输入区 -->
        <v-sheet elevation="0" color="transparent">
            <v-container max-width="800" class="px-6 pb-5 pt-2">
                <MessageInput v-model="input" :loading="loading" @send="send" @stop="stop" />
            </v-container>
        </v-sheet>
    </v-container>
</template>


<style scoped></style>


<script setup lang="ts">
    import MessageInput from '@/components/chat/MessageInput.vue'
    import TypingIndicator from '@/components/chat/TypingIndicator.vue'
    import ThinkingChain from '@/components/chat/ThinkingChain.vue'
    import MarkdownRenderer from '@/components/chat/MarkdownRenderer.vue'
    import type { ThinkingStep } from '@/types/conversation.ts'
    import { chatCompletion } from '@/api/conversation'
    import { generateUUID } from '@/api/conversation'
    import { pendingPrompt } from '@/utils/pendingPrompt'
    import { useAppStore } from '@/stores/app'
    import type {
        SseHistoryData,
        SseThoughtStepData,
        SseMessageDeltaData,
        SseDoneData,
        SseErrorData,
        SseSetTitleData,
        ThoughtStepType,
    } from '@/api/conversation'

    const route = useRoute()
    const conversationId = computed(() => route.params.conversationId as string)
    const appStore = useAppStore()

    const scrollEl = ref<InstanceType<typeof import('vuetify/components').VSheet> | null>(null)
    const input = ref('')
    const loading = ref(false)

    interface Message {
        role: 'user' | 'assistant'
        content: string
        time: string
        /** 思维链步骤列表，仅 assistant 消息可能有 */
        thinkingSteps?: ThinkingStep[]
        /** 思维链是否仍在推入新节点 */
        thinkingActive?: boolean
    }

    const now = () => new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

    const messages = reactive<Message[]>([])

    /** 当前是否有正在活跃的思维链（用于决定是否显示 TypingIndicator） */
    const hasActiveThinking = computed(() =>
        messages.some(m => m.thinkingActive)
    )

    const scrollToBottom = async () => {
        await nextTick()
        const el = scrollEl.value?.$el as HTMLElement | undefined
        if (el) el.scrollTop = el.scrollHeight
    }

    /** 仅当用户已在底部附近（150px 内）时才自动滚动，避免打断用户的阅读 */
    const scrollIfAtBottom = async () => {
        await nextTick()
        const el = scrollEl.value?.$el as HTMLElement | undefined
        if (!el) return
        const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
        if (distanceFromBottom <= 150) el.scrollTop = el.scrollHeight
    }

    /** 将后端 ThoughtStepType 映射到前端 ThinkingChain 所用的 type */
    const mapStepType = (type: ThoughtStepType): ThinkingStep['type'] => {
        if (type === 'tool_call') return 'tool'
        if (type === 'tool_response') return 'tool'
        return 'think'
    }

    /** 当前正在进行的流控制器，用于 stop 按钮 */
    let currentAbortCtrl: AbortController | null = null

    const processMessage = async (text: string) => {
        messages.push({ role: 'user', content: text, time: now() })
        await scrollToBottom()

        loading.value = true

        // 预先创建 assistant 消息占位，直接 push 到 reactive 数组
        // 用对象引用而非下标追踪，避免 onHistory splice 替换数组后下标失效
        const assistantMsg: Message = reactive({
            role: 'assistant',
            content: '',
            time: '',
            thinkingSteps: [],
            thinkingActive: false,
        })
        messages.push(assistantMsg)

        await scrollToBottom()

        const requestId = generateUUID()

        currentAbortCtrl = chatCompletion(
            {
                conversation_id: conversationId.value,
                request_id: requestId,
                content: text,
                create_at: Date.now(),
                need_history: false,
            },
            {
                onHistory: (data: SseHistoryData) => {
                    // 若后端推送了历史，重建消息列表（首次进入对话时）
                    // 注意：splice 会替换整个数组，需在末尾重新追加占位消息
                    if (!data.history_messages) return
                    messages.splice(0, messages.length, ...data.history_messages.map(m => ({
                        role: m.role as 'user' | 'assistant',
                        content: m.content,
                        time: new Date(m.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
                        thinkingSteps: m.thought_steps.map(s => ({
                            id: s.id,
                            type: mapStepType(s.type),
                            title: s.type,
                            content: s.content,
                            status: s.status === 'running' ? 'running' : 'done',
                            time: s.created_at ? new Date(s.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '',
                        } as ThinkingStep)),
                        thinkingActive: false,
                    })))
                    // splice 后重新将 assistantMsg 占位追加到末尾，保持引用有效
                    messages.push(assistantMsg)
                    void scrollToBottom()
                },

                onThoughtStep: (data: SseThoughtStepData) => {
                    assistantMsg.thinkingActive = true
                    const stepTime = data.step.created_at
                        ? new Date(data.step.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
                        : now()
                    // 按 id upsert：同一个 step 可能多次到达（running → done）
                    const existing = assistantMsg.thinkingSteps!.find(s => s.id === data.step.id)
                    if (existing) {
                        existing.content = data.step.content
                        existing.status = data.step.status === 'running' ? 'running' : 'done'
                        existing.time = stepTime
                    } else {
                        assistantMsg.thinkingSteps!.push({
                            id: data.step.id,
                            type: mapStepType(data.step.type),
                            title: data.step.type,
                            content: data.step.content,
                            status: data.step.status === 'running' ? 'running' : 'done',
                            time: stepTime,
                        })
                    }
                    void scrollIfAtBottom()
                },

                onMessageDelta: (data: SseMessageDeltaData) => {
                    assistantMsg.thinkingActive = false
                    assistantMsg.content += data.delta
                    void scrollIfAtBottom()
                },

                onDone: (_data: SseDoneData) => {
                    assistantMsg.thinkingActive = false
                    assistantMsg.time = now()
                    loading.value = false
                    currentAbortCtrl = null
                },

                onSetTitle: (data: SseSetTitleData) => {
                    // 通知侧边栏(c.vue)更新标题
                    appStore.setConversationTitle(data.conversation_id, data.title)
                },

                onError: (data: SseErrorData) => {
                    assistantMsg.thinkingActive = false
                    assistantMsg.content = `[错误] ${data.error_message}`
                    assistantMsg.time = now()
                    loading.value = false
                    currentAbortCtrl = null
                },

                onFetchError: (err) => {
                    console.error('[SSE] fetch error:', err)
                    assistantMsg.thinkingActive = false
                    assistantMsg.content = '[网络错误，请重试]'
                    assistantMsg.time = now()
                    loading.value = false
                    currentAbortCtrl = null
                },
            }
        )
    }

    /** 加载对话（首次进入或切换 conversationId 时） */
    const loadConversation = async () => {
        // 停止上一个流
        currentAbortCtrl?.abort()
        currentAbortCtrl = null
        messages.splice(0)
        loading.value = false

        const prompt = pendingPrompt.value
        if (prompt) {
            pendingPrompt.value = null
            await processMessage(prompt)
        } else {
            // 无初始 prompt，发送一个 need_history=true 的空请求拉取历史
            loading.value = true
            currentAbortCtrl = chatCompletion(
                {
                    conversation_id: conversationId.value,
                    request_id: generateUUID(),
                    create_at: Date.now(),
                    need_history: true,
                },
                {
                    onHistory: (data: SseHistoryData) => {
                        if (!data.history_messages) { loading.value = false; return }
                        messages.splice(0, messages.length, ...data.history_messages.map(m => ({
                            role: m.role as 'user' | 'assistant',
                            content: m.content,
                            time: new Date(m.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
                            thinkingSteps: m.thought_steps.map(s => ({
                                id: s.id,
                                type: mapStepType(s.type),
                                title: s.type,
                                content: s.content,
                                status: 'done' as const,
                                time: s.created_at ? new Date(s.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '',
                            } as ThinkingStep)),
                            thinkingActive: false,
                        })))
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

    // 初始加载
    onMounted(() => {
        loadConversation()
    })

    // 监听路由参数变化，切换对话时重新加载
    watch(conversationId, () => {
        loadConversation()
    })

    const send = async () => {
        const text = input.value.trim()
        if (!text || loading.value) return
        input.value = ''
        await processMessage(text)
    }

    const stop = () => {
        currentAbortCtrl?.abort()
        currentAbortCtrl = null
        loading.value = false
        const last = messages[messages.length - 1]
        if (last?.role === 'assistant') {
            last.thinkingActive = false
            if (!last.time) last.time = now()
        }
    }

    const copy = (text: string) => navigator.clipboard.writeText(text)
</script>
