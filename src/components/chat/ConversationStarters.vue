<template>
    <!-- 快捷建议卡片：chip 居中密排 -->
    <v-row justify="center" class="mb-4" style="max-width:480px" density="compact">
        <v-col v-for="s in suggestions" :key="s" cols="auto" class="pa-0 ma-0">
            <v-chip rounded="lg" variant="tonal" size="default" @click="emit('select', s)">
                {{ s }}
            </v-chip>
        </v-col>
    </v-row>
</template>

<script setup lang="ts">
    const emit = defineEmits<{
        (e: 'select', prompt: string): void
    }>()

    const suggestions = [
        '有哪些反直觉的数学问题',
        '我做错了这道题，请帮我分析原因',
        '请帮我总结以下课程的核心要点',
        '请解释一下为什么薄荷糖中间有一个洞？',
    ]
</script>
