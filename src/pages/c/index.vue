<template>
    <v-container class="h-100 d-flex flex-column align-center justify-center">
        <v-sheet width="100%" max-width="700" class="d-flex flex-column align-center" color="transparent">

            <!-- Logo & 欢迎语 -->
            <v-icon size="52" color="primary" class="mb-4">mdi-robot-happy-outline</v-icon>
            <v-card-title class="text-h6 font-weight-bold pa-0 mb-10">有什么我能帮你的吗？</v-card-title>

            <!-- 破冰提问 -->
            <ConversationStarters @select="input = $event" />

            <!-- 消息输入框 -->
            <MessageInput v-model="input" @send="send" />

        </v-sheet>
    </v-container>
</template>

<script setup lang="ts">
    import ConversationStarters from '@/components/ConversationStarters.vue'
    import MessageInput from '@/components/MessageInput.vue'

    const router = useRouter()
    const input = ref('')

    const send = () => {
        if (!input.value.trim()) return
        // TODO: 创建新对话并携带初始消息跳转
        router.push('/c/new')
    }
</script>
