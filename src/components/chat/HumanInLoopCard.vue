<template>
    <v-sheet rounded="lg" border class="my-2 pa-3 text-body-large">
        <!-- 标题行：工具名左侧，审批标签右侧 -->
        <div class="d-flex align-center mb-2">
            <v-icon size="16" color="warning" class="mr-2">mdi-shield-alert-outline</v-icon>
            <span class="font-weight-medium">{{ tool.tool_name }}</span>
            <v-spacer />
            <v-chip size="x-small" color="warning" variant="flat">需要审批</v-chip>
        </div>

        <!-- 审核意见 -->
        <div v-if="tool.pending_reason" class="d-flex align-start ga-2 mb-2 text-medium-emphasis">
            <v-icon size="14" class="mt-1 flex-shrink-0">mdi-robot-outline</v-icon>
            <span class="font-italic">{{ tool.pending_reason }}</span>
        </div>

        <!-- 参数（markdown 代码块） -->
        <div v-if="tool.tool_arguments && tool.tool_arguments.length > 0" class="mb-3">
            <MarkdownRenderer :content="formatArgsBlock(tool)" />
        </div>

        <!-- 按钮：右对齐 -->
        <div class="d-flex justify-end ga-1">
            <v-btn color="error" variant="tonal" size="small" rounded @click="$emit('action', 'reject')">
                <v-icon start size="16">mdi-close-circle-outline</v-icon>
                拒绝
            </v-btn>
            <v-btn variant="tonal" size="small" rounded @click="$emit('action', 'skip')">
                <v-icon start size="16">mdi-debug-step-over</v-icon>
                跳过
            </v-btn>
            <v-btn color="success" variant="flat" size="small" rounded @click="$emit('action', 'approve')">
                <v-icon start size="16">mdi-check-circle-outline</v-icon>
                批准
            </v-btn>
        </div>
    </v-sheet>
</template>

<script setup lang="ts">
    import type { ToolCallMessage } from '@/types/conversation'
    import MarkdownRenderer from '@/components/chat/MarkdownRenderer.vue'

    defineProps<{
        tool: ToolCallMessage
    }>()

    defineEmits<{
        action: [action: 'approve' | 'skip' | 'reject']
    }>()

    const formatArgsBlock = (tool: ToolCallMessage) => {
        if (!tool.tool_arguments || tool.tool_arguments.length === 0) return ''
        const obj = Object.fromEntries(
            tool.tool_arguments.map(a => [a.argument_name, a.argument])
        )
        return '```json\n' + JSON.stringify(obj, null, 2) + '\n```'
    }
</script>
