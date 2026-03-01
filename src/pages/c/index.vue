<template>
    <v-container class="h-100 d-flex flex-column align-center justify-center">
        <v-sheet width="100%" max-width="700" class="d-flex flex-column align-center" color="transparent">

            <!-- Logo & 欢迎语 -->
            <v-icon size="52" color="primary" class="mb-4">mdi-robot-happy-outline</v-icon>
            <v-card-title class="text-h6 font-weight-bold pa-0 mb-10">有什么我能帮你的吗？</v-card-title>

            <!-- 快捷建议卡片 -->
            <v-row justify="center" class="mb-6" density="compact">
                <v-col v-for="s in suggestions" :key="s.label" cols="6" sm="3" class="pa-2">
                    <v-card rounded="lg" variant="outlined" hover @click="startWith(s.prompt)" height="100%">
                        <v-card-text class="pa-3">
                            <v-row align="center" class="mb-1">
                                <v-icon size="small" :color="s.color" class="mr-2">{{ s.icon }}</v-icon>
                                <span class="text-caption font-weight-medium">{{ s.label }}</span>
                            </v-row>
                            <v-card-subtitle class="pa-0 text-caption text-wrap">{{ s.desc }}</v-card-subtitle>
                        </v-card-text>
                    </v-card>
                </v-col>
            </v-row>

            <!-- 输入框 -->
            <v-textarea v-model="input" placeholder="输入消息…" variant="outlined" rounded="lg" rows="3" auto-grow
                max-rows="8" hide-details class="w-100" @keydown.enter.exact.prevent="send">
                <template #append-inner>
                    <v-btn icon="mdi-send" size="small" :color="input.trim() ? 'primary' : undefined"
                        :disabled="!input.trim()" variant="text" :ripple="false" @click="send" />
                </template>
            </v-textarea>
            <v-card-subtitle class="pa-0 mt-2">按 Enter 发送 · Shift+Enter 换行</v-card-subtitle>
        </v-sheet>
    </v-container>
</template>

<script setup lang="ts">
    const router = useRouter()
    const input = ref('')

    const suggestions = [
        {
            icon: 'mdi-lightbulb-outline',
            color: 'amber',
            label: '头脑风暴',
            desc: '帮我生成一些创意点子',
            prompt: '帮我生成一些创意点子',
        },
        {
            icon: 'mdi-code-tags',
            color: 'blue',
            label: '写代码',
            desc: '帮我写或解释一段代码',
            prompt: '帮我写一段代码：',
        },
        {
            icon: 'mdi-text-box-edit-outline',
            color: 'green',
            label: '写作润色',
            desc: '帮我优化或翻译文字',
            prompt: '帮我润色以下文字：',
        },
        {
            icon: 'mdi-magnify',
            color: 'purple',
            label: '答疑解惑',
            desc: '解释一个概念或问题',
            prompt: '请解释一下：',
        },
    ]

    const startWith = (prompt: string) => {
        input.value = prompt
    }

    const send = () => {
        if (!input.value.trim()) return
        // TODO: 创建新对话并携带初始消息跳转
        router.push('/c/new')
    }
</script>
