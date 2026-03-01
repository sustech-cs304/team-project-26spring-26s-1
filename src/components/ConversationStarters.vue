<template>
    <!-- 快捷建议卡片 -->
    <v-row justify="center" class="mb-6" density="compact">
        <v-col v-for="s in suggestions" :key="s.label" cols="6" sm="3" class="pa-2">
            <v-card rounded="lg" variant="outlined" hover @click="emit('select', s.prompt)" height="100%">
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
</template>

<script setup lang="ts">
    const emit = defineEmits<{
        (e: 'select', prompt: string): void
    }>()

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
</script>
