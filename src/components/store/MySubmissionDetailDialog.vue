<template>
    <v-dialog :model-value="modelValue" max-width="760" @update:model-value="emit('update:modelValue', $event)">
        <v-card rounded="lg" class="submission-dialog">
            <div class="submission-header">
                <div class="min-w-0">
                    <div class="d-flex align-center ga-2">
                        <div class="submission-title">
                            {{ skill?.name ?? '投稿详情' }}
                        </div>
                        <v-chip v-if="skill" size="x-small" rounded="lg" :color="getStatusColor(skill.status)"
                            variant="tonal">
                            {{ getStatusText(skill.status) }}
                        </v-chip>
                    </div>

                    <div v-if="skill" class="submission-meta">
                        <span>{{ formatDownloads(skill.download_count) }} 次下载</span>
                        <span>{{ formatDate(skill.created_at) }}</span>
                    </div>
                </div>

                <v-btn icon="mdi-close" size="small" variant="text" :ripple="false"
                    @click="emit('update:modelValue', false)" />
            </div>

            <v-card-text class="submission-body">
                <template v-if="skill">
                    <v-alert v-if="skill.status === 'rejected' && skill.rejection_reason" type="error" variant="tonal"
                        rounded="lg" density="compact" class="mb-2" icon="mdi-alert-circle-outline">
                        {{ skill.rejection_reason }}
                    </v-alert>

                    <v-sheet v-else rounded="lg" border color="transparent" class="submission-status mb-2">
                        <div class="font-weight-bold">{{ getStatusText(skill.status) }}</div>
                        <div class="text-medium-emphasis">
                            {{ getStatusDescription(skill.status) }}
                        </div>
                    </v-sheet>

                    <div v-if="skill.tags.length" class="submission-tags">
                        <v-chip v-for="tag in skill.tags" :key="tag.id" size="x-small" rounded="lg" variant="outlined">
                            {{ tag.name }}
                        </v-chip>
                    </div>

                    <v-sheet rounded="lg" border color="transparent" class="submission-markdown">
                        <MarkdownRenderer :content="skill.markdown_content || '暂无详情内容。'" />
                    </v-sheet>
                </template>

                <div v-else class="text-body-2 text-medium-emphasis">
                    暂无详情内容。
                </div>
            </v-card-text>

            <v-card-actions class="submission-actions">
                <v-spacer />
                <v-btn size="small" variant="text" rounded="lg" @click="emit('update:modelValue', false)">
                    关闭
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script setup lang="ts">
    import MarkdownRenderer from '@/components/chat/MarkdownRenderer.vue'
    import type { StoreMySkill } from '@/types/store'

    defineProps<{
        modelValue: boolean
        skill: StoreMySkill | null
    }>()

    const emit = defineEmits<{
        'update:modelValue': [value: boolean]
    }>()

    function formatDownloads (count: number) {
        if (count >= 1000000) return `${(count / 1000000).toFixed(1)}m`
        if (count >= 1000) return `${(count / 1000).toFixed(1)}k`
        return String(count)
    }

    function formatDate (raw: string) {
        const date = new Date(raw)
        if (Number.isNaN(date.getTime())) return raw || '-'

        return date.toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        })
    }

    function getStatusText (status: StoreMySkill['status']) {
        switch (status) {
            case 'pending': return '审核中'
            case 'approved': return '已上架'
            case 'rejected': return '已拒绝'
            case 'archived': return '已归档'
            default: return status
        }
    }

    function getStatusColor (status: StoreMySkill['status']) {
        switch (status) {
            case 'pending': return 'warning'
            case 'approved': return 'success'
            case 'rejected': return 'error'
            case 'archived': return 'grey'
            default: return 'default'
        }
    }

    function getStatusDescription (status: StoreMySkill['status']) {
        switch (status) {
            case 'pending': return '当前投稿正在审核中。'
            case 'approved': return '该技能已通过审核并上架。'
            case 'archived': return '该技能已下架，当前不会在技能商店展示。'
            case 'rejected': return '该技能未通过审核。'
            default: return ''
        }
    }
</script>

<style scoped>
    .submission-dialog {
        display: flex;
        overflow: hidden;
        max-height: min(86vh, 820px);
        flex-direction: column;
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    }

    .submission-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 12px 14px;
        border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    }

    .submission-title {
        overflow: hidden;
        font-size: 1rem;
        font-weight: 700;
        line-height: 1.35rem;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .submission-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-top: 4px;
        color: rgba(var(--v-theme-on-surface), 0.58);
        font-size: 0.75rem;
        font-weight: 600;
    }

    .submission-body {
        overflow-y: auto;
        padding: 12px 14px;
    }

    .submission-status {
        padding: 10px 12px;
        font-size: 0.8125rem;
    }

    .submission-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 10px;
    }

    .submission-markdown {
        padding: 14px;
        background: rgba(var(--v-theme-on-surface), 0.018) !important;
    }

    .submission-actions {
        padding: 8px 14px 12px;
        border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    }
</style>
