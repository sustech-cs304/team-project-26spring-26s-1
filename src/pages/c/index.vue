<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0">

        <!-- 中间内容区：垂直居中 -->
        <v-sheet color="transparent" class="flex-grow-1 d-flex flex-column align-center justify-center">
            <v-container max-width="800" class="px-6 d-flex flex-column align-center">
                <div class="text-display-small font-weight-bold pa-0 mb-10">有什么我能帮你的吗？</div>
                <ConversationStarters @select="input = $event" />
            </v-container>
        </v-sheet>

        <!-- 底部输入区 -->
        <v-sheet elevation="0" color="transparent">
            <v-container max-width="800" class="px-6 pb-5 pt-2">
                <MessageInput v-model="input" @send="send" />
            </v-container>
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
