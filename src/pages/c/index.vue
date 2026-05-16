<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0 overflow-hidden min-height-0">

        <!-- 中间内容区：垂直居中 -->
        <v-sheet color="transparent"
            class="flex-grow-1 d-flex flex-column align-center justify-center min-height-0 overflow-hidden">
            <v-container max-width="800" class="chat-empty-guide px-6 d-flex flex-column align-center min-height-0">
                <div class="text-display-small font-weight-bold pa-0 mb-10">有什么我能帮你的吗？</div>
                <ConversationStarters @select="startConversation" />
            </v-container>
        </v-sheet>

        <!-- 底部输入区 -->
        <v-sheet elevation="0" color="transparent" class="flex-shrink-0">
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
    import { useAppStore } from '@/stores/app'
    import { pendingPrompt } from '@/utils/pendingPrompt'
    import type { AttachmentFile, UserMessageAttachment } from '@/types/attachment'

    const router = useRouter()
    const appStore = useAppStore()
    type MessageInputExposed = InstanceType<typeof MessageInput> & {
        getAttachmentsSnapshot?: () => AttachmentFile[]
        clearAttachments?: () => void
    }
    const messageInputRef = ref<MessageInputExposed | null>(null)
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

    const toPendingAttachment = (attachment: AttachmentFile): UserMessageAttachment => ({
        id: attachment.fileId || attachment.id,
        fileId: attachment.fileId,
        name: attachment.name,
        category: attachment.category,
        size: attachment.size,
        dataUrl: attachment.dataUrl,
        status: 'ready',
        source: 'local',
    })

    const startConversation = async (prompt: string, attachments: UserMessageAttachment[] = []) => {
        creating.value = true
        try {
            const conv = await createConversation()
            appStore.setConversationCreated({
                conversation_id: conv.conversation_id,
                created_at: conv.created_at,
                updated_at: conv.created_at,
                title: 'New Conversation',
                is_active: true,
                is_pinned: false,
            })
            pendingPrompt.value = {
                content: prompt,
                attachments,
            }
            router.push(`/c/${conv.conversation_id}`)
        } catch (err) {
            console.error('创建对话失败:', err)
        } finally {
            creating.value = false
        }
    }

    const send = () => {
        const text = input.value.trim()
        const attachments = messageInputRef.value?.getAttachmentsSnapshot?.() ?? []
        if ((!text && attachments.length === 0) || creating.value) return
        input.value = ''
        messageInputRef.value?.clearAttachments?.()
        startConversation(text, attachments.map(toPendingAttachment))
    }
</script>

<style scoped>
    .chat-empty-guide {
        transform: translateY(-48px);
    }

    @media (max-height: 720px) {
        .chat-empty-guide {
            transform: translateY(-28px);
        }
    }
</style>
