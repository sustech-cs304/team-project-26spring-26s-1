<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0">

        <!-- 中间内容区：垂直居中 -->
        <v-sheet color="transparent" class="flex-grow-1 d-flex flex-column align-center justify-center">
            <v-container max-width="800" class="px-6 d-flex flex-column align-center">
                <div class="text-display-small font-weight-bold pa-0 mb-10">有什么我能帮你的吗？</div>
                <ConversationStarters @select="startConversation" />
            </v-container>
        </v-sheet>

        <!-- 底部输入区 -->
        <v-sheet elevation="0" color="transparent">
            <v-container max-width="800" class="px-6 pb-5 pt-2">
                <MessageInput ref="messageInputRef" v-model="input" :loading="creating" @send="send" />
            </v-container>
        </v-sheet>

    </v-container>
</template>

<script setup lang="ts">
    import ConversationStarters from '@/components/chat/ConversationStarters.vue'
    import MessageInput from '@/components/chat/MessageInput.vue'
    import { createConversation } from '@/api/conversation'
    import { pendingPrompt } from '@/utils/pendingPrompt'

    const router = useRouter()
    const messageInputRef = ref<InstanceType<typeof MessageInput> | null>(null)
    const input = ref('')
    const creating = ref(false)

    // ── 向布局层注册 MessageInput（用于拖拽上传） ──
    const registerMessageInput = inject<(ref: any) => void>('registerMessageInput')
    const unregisterMessageInput = inject<() => void>('unregisterMessageInput')

    onMounted(() => {
        registerMessageInput?.(messageInputRef.value)
    })

    onBeforeUnmount(() => {
        unregisterMessageInput?.()
    })

    watch(messageInputRef, (ref) => {
        if (ref) registerMessageInput?.(ref)
    })

    const startConversation = async (prompt: string) => {
        creating.value = true
        try {
            const conv = await createConversation()
            pendingPrompt.value = prompt
            router.push(`/c/${conv.conversation_id}`)
        } catch (err) {
            console.error('创建对话失败:', err)
        } finally {
            creating.value = false
        }
    }

    const send = () => {
        const text = input.value.trim()
        if (!text || creating.value) return
        startConversation(text)
    }
</script>
