<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0">

        <!-- 消息列表 -->
        <v-sheet ref="scrollEl" color="transparent" class="flex-grow-1 overflow-y-auto msg-scroll"
            :class="{ scrolling }">
            <v-container max-width="720" class="px-6 py-8">
                <template v-for="(msg, i) in messages" :key="i">

                    <!-- 用户消息 -->
                    <v-row v-if="msg.role === 'user'" justify="end" class="mb-4" no-gutters>
                        <v-col cols="auto" class="d-flex align-end ga-2" style="max-width: 78%;">
                            <v-sheet rounded="lg" color="primary" class="px-4 py-3 text-body-2"
                                style="white-space: pre-wrap; word-break: break-word; line-height: 1.6;">
                                {{ msg.content }}
                            </v-sheet>
                            <v-avatar size="30" color="primary" class="flex-shrink-0 mb-1">
                                <v-icon size="16">mdi-account</v-icon>
                            </v-avatar>
                        </v-col>
                    </v-row>

                    <!-- AI 消息 -->
                    <v-row v-else class="mb-1" no-gutters>
                        <v-col class="pa-0" style="min-width: 0; max-width: 78%;">
                            <v-sheet rounded="lg" color="transparent" class="px-4 py-3 text-body-2"
                                style="white-space: pre-wrap; word-break: break-word; line-height: 1.6;">
                                {{ msg.content }}
                            </v-sheet>
                            <v-row no-gutters align="center" class="mt-1 ml-2 ga-1 mb-3" style="opacity: 0.6;">
                                <span class="text-caption">{{ msg.time }}</span>
                                <v-btn icon="mdi-content-copy" size="x-small" variant="text" :ripple="false"
                                    density="compact" @click="copy(msg.content)" />
                                <v-btn icon="mdi-thumb-up-outline" size="x-small" variant="text" :ripple="false"
                                    density="compact" />
                                <v-btn icon="mdi-thumb-down-outline" size="x-small" variant="text" :ripple="false"
                                    density="compact" />
                            </v-row>
                        </v-col>
                    </v-row>

                </template>

                <!-- 加载中 -->
                <v-row v-if="loading" class="mb-4" no-gutters>
                    <v-col cols="auto">
                        <v-sheet rounded="lg" color="transparent" class="px-4 py-3 d-flex align-center ga-1">
                            <v-icon size="8" color="primary" class="dot-bounce"
                                style="animation-delay: 0ms">mdi-circle</v-icon>
                            <v-icon size="8" color="primary" class="dot-bounce"
                                style="animation-delay: 150ms">mdi-circle</v-icon>
                            <v-icon size="8" color="primary" class="dot-bounce"
                                style="animation-delay: 300ms">mdi-circle</v-icon>
                        </v-sheet>
                    </v-col>
                </v-row>
            </v-container>
        </v-sheet>

        <!-- 底部输入区 -->
        <v-sheet elevation="0" color="transparent">
            <v-container max-width="720" class="px-6 pb-5 pt-2">
                <v-textarea v-model="input" placeholder="发送消息，或输入 / 使用命令…" variant="outlined" rounded="lg" rows="1"
                    auto-grow max-rows="6" hide-details density="comfortable" @keydown.enter.exact.prevent="send">
                    <template #append-inner>
                        <v-row no-gutters align="center" class="ga-1 flex-nowrap">
                            <v-btn icon="mdi-paperclip" size="small" variant="text" :ripple="false" density="compact"
                                :disabled="loading" />
                            <v-btn icon="mdi-microphone-outline" size="small" variant="text" :ripple="false"
                                density="compact" :disabled="loading" />
                            <v-btn icon="mdi-arrow-up" size="32"
                                :color="input.trim() && !loading ? 'primary' : 'surface-variant'"
                                :variant="input.trim() && !loading ? 'flat' : 'tonal'"
                                :disabled="!input.trim() || loading" :ripple="false" rounded="lg" @click="send" />
                        </v-row>
                    </template>
                </v-textarea>
                <v-row no-gutters justify="center" class="mt-2">
                    <span class="text-caption text-disabled">按 Enter 发送 · Shift+Enter 换行</span>
                </v-row>
            </v-container>
        </v-sheet>
    </v-container>
</template>


<style scoped>

    .msg-scroll {
        scrollbar-gutter: stable;
    }

    .msg-scroll::-webkit-scrollbar {
        width: 6px;
    }

    .msg-scroll::-webkit-scrollbar-track {
        background: transparent;
    }

    .msg-scroll::-webkit-scrollbar-thumb {
        background: transparent;
        border-radius: 3px;
    }

    .msg-scroll.scrolling::-webkit-scrollbar-thumb {
        background: rgba(128, 128, 128, 0.45);
    }

    .dot-bounce {
        animation: bounce 1s ease-in-out infinite;
    }

    @keyframes bounce {

        0%,
        100% {
            transform: translateY(0);
            opacity: 0.4;
        }

        50% {
            transform: translateY(-4px);
            opacity: 1;
        }
    }
</style>


<script setup lang="ts">
    const route = useRoute()
    const conversationId = computed(() => route.params.conversationId)

    const scrollEl = ref<InstanceType<typeof import('vuetify/components').VSheet> | null>(null)
    const input = ref('')
    const loading = ref(false)
    const scrolling = ref(false)
    let scrollTimer: ReturnType<typeof setTimeout> | null = null

    onMounted(() => {
        const el = scrollEl.value?.$el as HTMLElement | undefined
        if (!el) return
        el.addEventListener('scroll', () => {
            scrolling.value = true
            if (scrollTimer) clearTimeout(scrollTimer)
            scrollTimer = setTimeout(() => { scrolling.value = false }, 1000)
        }, { passive: true })
    })

    onBeforeUnmount(() => {
        if (scrollTimer) clearTimeout(scrollTimer)
    })

    interface Message {
        role: 'user' | 'assistant'
        content: string
        time: string
    }

    const now = () => new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

    const messages = ref<Message[]>([
        { role: 'assistant', content: '你好！有什么我能帮你的吗？', time: now() },
    ])

    const scrollToBottom = async () => {
        await nextTick()
        const el = scrollEl.value?.$el as HTMLElement | undefined
        if (el) el.scrollTop = el.scrollHeight
    }

    const send = async () => {
        const text = input.value.trim()
        if (!text) return
        input.value = ''
        messages.value.push({ role: 'user', content: text, time: now() })
        await scrollToBottom()

        loading.value = true
        await scrollToBottom()
        // TODO: 接入真实 API
        await new Promise(r => setTimeout(r, 1200))
        loading.value = false
        messages.value.push({ role: 'assistant', content: `（模拟回复）你说的是："${text}"`, time: now() })
        await scrollToBottom()
    }

    const copy = (text: string) => navigator.clipboard.writeText(text)
</script>
