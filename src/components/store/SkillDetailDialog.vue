<template>
    <v-dialog :model-value="modelValue" max-width="920" @update:model-value="emit('update:modelValue', $event)">
        <v-card rounded="xl" style="border: 2px solid rgba(var(--v-border-color), var(--v-border-opacity));">
            <v-sheet class="px-6 px-md-8 pt-6 pb-4" style="border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));">
                <div class="d-flex align-start justify-space-between ga-4">
                    <div class="min-width-0">
                        <div class="d-flex align-center flex-wrap ga-2 mb-2">
                            <div class="text-h5 font-weight-bold text-truncate">
                                {{ skill?.name ?? '' }}
                            </div>
                            <v-chip
                                v-if="skill"
                                size="small"
                                rounded="lg"
                                :color="skill.install ? 'success' : 'default'"
                                :variant="skill.install ? 'tonal' : 'outlined'"
                            >
                                {{ skill.install ? '已安装' : '未安装' }}
                            </v-chip>
                        </div>

                        <div
                            v-if="skill"
                            class="d-flex flex-wrap ga-4"
                            style="font-size: 0.8rem; font-weight: 600; color: rgba(var(--v-theme-on-surface), 0.58);"
                        >
                            <span>Download count: {{ formatDownloads(skill.download_count) }}</span>
                            <span>Created at: {{ formatDate(skill.created_at) }}</span>
                        </div>
                    </div>

                    <v-btn icon variant="text" @click="emit('update:modelValue', false)">
                        <v-icon>mdi-close</v-icon>
                    </v-btn>
                </div>
            </v-sheet>

            <div class="px-6 px-md-8 pt-4 pb-0">
                <div v-if="skill" class="d-flex flex-wrap ga-2 mb-4">
                    <span
                        v-for="tag in skill.tags"
                        :key="tag.id"
                        style="padding: 5px 9px; border-radius: 999px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); color: rgb(var(--v-theme-on-surface)); font-size: 0.72rem; font-weight: 700;"
                    >
                        {{ tag.name }}
                    </span>
                </div>
            </div>

            <v-card-text class="px-6 px-md-8 pb-4" style="max-height: min(68vh, 760px); overflow-y: auto;">
                <v-skeleton-loader v-if="loading" type="article, article, article" />

                <template v-else-if="skill">
                    <v-sheet
                        v-if="skill.description"
                        class="text-body-1 mb-6"
                        style="line-height: 1.75; color: rgba(var(--v-theme-on-surface), 0.78);"
                    >
                        {{ skill.description }}
                    </v-sheet>

                    <v-sheet style="border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 18px; padding: 20px;">
                        <MarkdownRenderer :content="skill.markdown_content || '暂无详情内容。'" />
                    </v-sheet>
                </template>

                <div v-else class="text-body-2 text-medium-emphasis">
                    暂无详情内容。
                </div>
            </v-card-text>

            <v-card-actions class="px-6 px-md-8 pb-6">
                <v-spacer />
                <v-btn variant="text" rounded="lg" @click="emit('update:modelValue', false)">
                    关闭
                </v-btn>
                <v-btn
                    v-if="skill && !skill.install"
                    color="primary"
                    rounded="lg"
                    :loading="actionLoading"
                    @click="emit('install', skill)"
                >
                    下载
                </v-btn>
                <v-btn
                    v-else-if="skill"
                    color="error"
                    variant="outlined"
                    rounded="lg"
                    :loading="actionLoading"
                    @click="emit('remove', skill)"
                >
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

    function formatDownloads(count: number) {
        if (count >= 1000000) return `${(count / 1000000).toFixed(1)}m`
        if (count >= 1000) return `${(count / 1000).toFixed(1)}k`
        return String(count)
    }

    function formatDate(raw: string) {
        const date = new Date(raw)
        if (Number.isNaN(date.getTime())) return raw

        return date.toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        })
    }
</script>
