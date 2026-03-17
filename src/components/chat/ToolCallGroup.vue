<template>
    <div class="my-0">
        <!-- 折叠态按钮 -->
        <v-btn variant="text" size="small" class="text-body-medium opacity-80 pa-1" :height="28"
            @click="expanded = !expanded" :ripple="false">
            <v-icon size="14" class="mr-1">mdi-eye-outline</v-icon>
            View {{ steps.length }} step{{ steps.length > 1 ? 's' : '' }}
            <v-icon size="14" class="ml-1">{{ expanded ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
        </v-btn>

        <!-- 展开内容 -->
        <v-expand-transition>
            <div v-if="expanded" class="tool-group-detail">
                <div v-for="(tool, index) in steps" :key="`${tool.tool_name}-${index}`">
                    <!-- 工具名称行 -->
                    <v-list-item @click="toggleToolDetail(index)" class="px-1" density="compact" prepend-gap="6">
                        <template #prepend>
                            <v-icon size="14" color="medium-emphasis">mdi-wrench-outline</v-icon>
                        </template>

                        <v-list-item-title class="text-body-medium text-medium-emphasis">
                            {{ tool.tool_name }}
                        </v-list-item-title>

                        <template #append>
                            <v-chip v-if="tool.tool_response" size="x-small" color="success" variant="flat" class="mr-1">
                                Done
                            </v-chip>
                            <v-chip v-else-if="tool.status === 'pending'" size="x-small" color="warning" variant="text" class="mr-1">
                                <span class="typing-shimmer">Running</span>
                            </v-chip>
                            <v-chip v-else size="x-small" color="info" variant="flat" class="mr-1">
                                {{ tool.status }}
                            </v-chip>
                            <v-icon size="14" color="medium-emphasis">
                                {{ expandedIndexes.has(index) ? 'mdi-chevron-up' : 'mdi-chevron-down' }}
                            </v-icon>
                        </template>
                    </v-list-item>

                    <!-- 详细内容 -->
                    <v-expand-transition>
                        <div v-if="expandedIndexes.has(index)" class="ml-3">
                            <!-- 调用参数 -->
                            <div class="text-body-medium text-medium-emphasis mb-1 mt-2">调用参数</div>
                            <v-sheet rounded="lg" color="transparent" class="pa-0 mb-2">
                                <MarkdownRenderer :content="wrapCodeBlock(formatArgs(tool), 'json')" />
                            </v-sheet>

                            <!-- 响应内容 -->
                            <template v-if="tool.tool_response">
                                <div class="text-body-medium text-medium-emphasis mb-1">返回结果</div>
                                <v-sheet rounded="lg" color="transparent" class="pa-0">
                                    <MarkdownRenderer :content="wrapCodeBlock(tool.tool_response, 'json')" />
                                </v-sheet>
                            </template>
                        </div>
                    </v-expand-transition>
                </div>
            </div>
        </v-expand-transition>
    </div>
</template>

<script setup lang="ts">
    import type { ToolCallMessage } from '@/types/conversation'
    import MarkdownRenderer from '@/components/chat/MarkdownRenderer.vue'

    const props = defineProps<{
        steps: ToolCallMessage[]
        autoCollapse?: boolean
    }>()

    const expanded = ref(false)
    const expandedIndexes = ref<Set<number>>(new Set())

    /** 切换单个 tool 的详情展开状态 */
    const toggleToolDetail = (index: number) => {
        if (expandedIndexes.value.has(index)) {
            expandedIndexes.value.delete(index)
        } else {
            expandedIndexes.value.add(index)
        }
    }

    /** 将 tool_arguments 格式化为 JSON 字符串 */
    const formatArgs = (tool: ToolCallMessage) => {
        if (!tool.tool_arguments || tool.tool_arguments.length === 0) return '{}'
        const obj = Object.fromEntries(
            tool.tool_arguments.map(a => [a.argument_name, a.argument])
        )
        return JSON.stringify(obj, null, 2)
    }

    /** 将内容用 markdown code block 包裹 */
    const wrapCodeBlock = (content: string, language: string) => {
        if (content.trim().startsWith('```')) return content
        return `\`\`\`${language}\n${content}\n\`\`\``
    }

    // 监听 tool 状态，自动展开有 pending tool 的组
    watch(() => props.steps, (newSteps) => {
        const hasPending = newSteps.some(s => s.status === 'pending' && !s.tool_response)
        if (hasPending) {
            expanded.value = true
        }
    }, { immediate: true, deep: true })

    // 监听 autoCollapse 变化
    watch(() => props.autoCollapse, (shouldCollapse) => {
        if (shouldCollapse) {
            expanded.value = false
            expandedIndexes.value.clear()
        }
    })
</script>

<style scoped>
    .tool-group-detail {
        margin-left: 12px;
        padding-left: 8px;
        border-left: 2px solid rgba(var(--v-theme-on-surface), 0.12);
    }
</style>
