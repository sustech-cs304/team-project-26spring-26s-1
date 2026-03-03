<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0">

        <!-- 消息列表 -->
        <v-sheet ref="scrollEl" color="transparent" class="flex-grow-1 overflow-y-auto">
            <v-container max-width="800" class="px-6 py-4">
                <template v-for="(msg, i) in messages" :key="i">

                    <!-- 用户消息 -->
                    <v-row v-if="msg.role === 'user'" justify="end" class="mb-1" density="compact">
                        <v-col cols="auto" class="d-flex align-end ga-2" style="max-width: 83%;">
                            <v-sheet rounded="lg" color="" class="px-3 py-2"
                                style="white-space: pre-wrap; word-break: break-word; line-height: 1.6;">
                                {{ msg.content }}
                            </v-sheet>
                            <v-avatar size="30" class="flex-shrink-0">
                                <v-icon size="16">mdi-account</v-icon>
                            </v-avatar>
                        </v-col>
                    </v-row>

                    <!-- AI 消息 -->
                    <v-row v-else-if="msg.role === 'assistant'" class="mb-1" density="compact">
                        <v-col class="pa-0" style="min-width: 0; max-width: 100%;">
                            <v-sheet rounded="lg" color="transparent" class="px-0 py-2"
                                style="white-space: pre-wrap; word-break: break-word; line-height: 1.6;">
                                {{ msg.content }}
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

                <!-- 加载中 -->
                <TypingIndicator v-if="loading" />
            </v-container>
        </v-sheet>

        <!-- 底部输入区 -->
        <v-sheet elevation="0" color="transparent">
            <v-container max-width="800" class="px-6 pb-5 pt-2">
                <MessageInput v-model="input" :loading="loading" @send="send" />
            </v-container>
        </v-sheet>
    </v-container>
</template>


<style scoped></style>


<script setup lang="ts">
    import MessageInput from '@/components/MessageInput.vue'
    import TypingIndicator from '@/components/TypingIndicator.vue'

    const route = useRoute()
    const conversationId = computed(() => route.params.conversationId)

    const scrollEl = ref<InstanceType<typeof import('vuetify/components').VSheet> | null>(null)
    const input = ref('')
    const loading = ref(false)

    interface Message {
        role: 'user' | 'assistant'
        content: string
        time: string
    }

    const now = () => new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

    const messages = ref<Message[]>([])

    const scrollToBottom = async () => {
        await nextTick()
        const el = scrollEl.value?.$el as HTMLElement | undefined
        if (el) el.scrollTop = el.scrollHeight
    }

    // 处理对话核心逻辑
    const processMessage = async (text: string) => {
        messages.value.push({ role: 'user', content: text, time: now() })
        await scrollToBottom()

        loading.value = true
        await scrollToBottom()

        // TODO: 接入真实 API
        await new Promise(r => setTimeout(r, 1200))

        loading.value = false
        messages.value.push({ role: 'assistant', content: `(模拟回复)你说的是："${text}"`, time: now() })
        await scrollToBottom()
    }

    const loadConversation = async () => {
        messages.value = []
        loading.value = true

        // 模拟网络延迟
        await new Promise(r => setTimeout(r, 600))

        const state = history.state as { prompt?: string }
        if (state.prompt) {
            const prompt = state.prompt
            history.replaceState({ ...history.state, prompt: undefined }, '')
            loading.value = false
            await processMessage(prompt)
        } else {
            // 简单的随机生成不同对话演示
            const random = Math.random()
            if (random > 0.5) {
                messages.value = [
                    { role: 'user', content: 'Vue 3 的生命周期有哪些？', time: '09:30' },
                    { role: 'assistant', content: 'Vue 3 的主要生命周期钩子包括 onMounted, onUpdated, onUnmounted 等，配合 Composition API 使用。', time: '09:31' },
                ]
            } else {
                messages.value = [
                    { role: 'user', content: 'Rust 语言适合写前端吗？', time: '14:20' },
                    { role: 'assistant', content: 'Rust 可以通过 WebAssembly (Wasm) 编写前端高性能模块，通常配合 Yew 或 Leptos 框架使用。', time: '14:21' },
                ]
            }
            loading.value = false
            await scrollToBottom()
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
        if (!text) return
        input.value = ''
        await processMessage(text)
    }

    const copy = (text: string) => navigator.clipboard.writeText(text)
</script>
