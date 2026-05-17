<template>
    <v-dialog :model-value="modelValue" max-width="760" @update:model-value="emit('update:modelValue', $event)">
        <v-card rounded="lg" class="skill-detail-dialog">
            <div class="skill-detail-header">
                <div class="min-w-0">
                    <div class="d-flex align-center ga-2">
                        <div class="skill-detail-title">
                            {{ skill?.name ?? '技能详情' }}
                        </div>
                        <v-chip v-if="skill" size="x-small" rounded="lg" variant="tonal">
                            {{ skill.install ? '已安装' : '未安装' }}
                        </v-chip>
                    </div>
                    <div v-if="skill" class="skill-detail-meta">
                        <span>{{ formatDownloads(skill.download_count) }} 次下载</span>
                        <span>{{ formatDate(skill.created_at) }}</span>
                    </div>
                </div>

                <v-btn icon="mdi-close" size="small" variant="text" :ripple="false"
                    @click="emit('update:modelValue', false)" />
            </div>

            <v-card-text class="skill-detail-body">
                <v-skeleton-loader v-if="loading" type="article, article" />

                <template v-else-if="skill">
                    <div v-if="skill.tags.length" class="skill-detail-tags">
                        <v-chip v-for="tag in skill.tags" :key="tag.id" size="x-small" rounded="lg" variant="tonal">
                            {{ tag.name }}
                        </v-chip>
                    </div>

                    <v-sheet rounded="lg" border color="transparent" class="skill-detail-markdown">
                        <MarkdownRenderer :content="skill.markdown_content || '暂无详情内容。'" />
                    </v-sheet>
                </template>

                <div v-else class="text-body-2 text-medium-emphasis">
                    暂无详情内容。
                </div>
            </v-card-text>

            <v-card-actions class="skill-detail-actions">
                <v-spacer />
                <v-btn size="small" variant="text" rounded="lg" @click="emit('update:modelValue', false)">
                    关闭
                </v-btn>
                <v-btn v-if="skill && !skill.install" size="small" variant="tonal" rounded="lg"
                    prepend-icon="mdi-download-outline" :loading="actionLoading"
                    @click="emit('install', skill)">
                    下载
                </v-btn>
                <v-btn v-else-if="skill" size="small" variant="tonal" rounded="lg"
                    prepend-icon="mdi-trash-can-outline" :loading="actionLoading" @click="emit('remove', skill)">
                    卸载
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script setup lang="ts">
    import MarkdownRenderer from '@/components/chat/MarkdownRenderer.vue'
    import type { StoreSkillDetail } from '@/types/store'

    defineProps<{
        modelValue: boolean
        skill: StoreSkillDetail | null
        loading: boolean
        actionLoading: boolean
    }>()

    const emit = defineEmits<{
        'update:modelValue': [value: boolean]
        install: [skill: StoreSkillDetail]
        remove: [skill: StoreSkillDetail]
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
</script>

<style scoped>
    .skill-detail-dialog {
        overflow: hidden;
        border: 1px solid rgba(var(--v-border-color), 0.16);
    }

    .skill-detail-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 12px 14px;
        border-bottom: 1px solid rgba(var(--v-border-color), 0.14);
    }

    .skill-detail-title {
        overflow: hidden;
        font-size: 1rem;
        font-weight: 700;
        line-height: 1.35rem;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .skill-detail-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-top: 4px;
        color: rgba(var(--v-theme-on-surface), 0.58);
        font-size: 0.75rem;
        font-weight: 600;
    }

    .skill-detail-body {
        max-height: min(68vh, 720px);
        overflow-y: auto;
        padding: 12px 14px;
    }

    .skill-detail-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 10px;
    }

    .skill-detail-markdown {
        padding: 14px;
        background: rgba(var(--v-theme-on-surface), 0.018) !important;
    }

    .skill-detail-actions {
        padding: 8px 14px 12px;
        border-top: 1px solid rgba(var(--v-border-color), 0.14);
    }
</style>
