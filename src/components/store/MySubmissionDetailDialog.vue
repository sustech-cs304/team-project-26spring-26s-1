<template>
    <v-dialog :model-value="modelValue" max-width="920" @update:model-value="emit('update:modelValue', $event)">
        <v-card rounded="xl" style="border: 2px solid rgba(var(--v-border-color), var(--v-border-opacity));max-height: min(86vh, 920px);display: flex;flex-direction: column; overflow: hidden;">
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
                                :color="getStatusColor(skill.status)"
                                variant="tonal"
                            >
                                {{ getStatusText(skill.status) }}
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

            <v-card-text class="px-6 px-md-8 pb-4" style="max-height: min(68vh, 760px); overflow-y: auto;" >
                <template v-if="skill">
                    <v-alert
                        v-if="skill.status === 'rejected' && skill.rejection_reason"
                        type="error"
                        variant="tonal"
                        rounded="lg"
                        class="mb-4"
                        icon="mdi-alert-circle-outline"
                    >
                        <div class="font-weight-bold mb-1">审核未通过</div>
                        <div>{{ skill.rejection_reason }}</div>
                    </v-alert>

                    <v-sheet
                        v-else-if="skill.status === 'pending'"
                        class="mb-4 pa-4"
                        rounded="lg"
                        style="background: rgba(var(--v-theme-warning), 0.08); border: 1px solid rgba(var(--v-theme-warning), 0.24);"
                    >
                        <div class="font-weight-bold mb-1">审核状态</div>
                        <div class="text-body-2 text-medium-emphasis">当前投稿正在审核中，请耐心等待结果。</div>
                    </v-sheet>

                    <v-sheet
                        v-else-if="skill.status === 'approved'"
                        class="mb-4 pa-4"
                        rounded="lg"
                        style="background: rgba(var(--v-theme-success), 0.08); border: 1px solid rgba(var(--v-theme-success), 0.24);"
                    >
                        <div class="font-weight-bold mb-1">审核状态</div>
                        <div class="text-body-2 text-medium-emphasis">该技能已通过审核并上架。</div>
                    </v-sheet>

                    <v-sheet
                        v-else-if="skill.status === 'archived'"
                        class="mb-4 pa-4"
                        rounded="lg"
                        style="background: rgba(var(--v-theme-on-surface), 0.04); border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));"
                    >
                        <div class="font-weight-bold mb-1">审核状态</div>
                        <div class="text-body-2 text-medium-emphasis">该技能已下架，当前不会在技能商店展示。</div>
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

    function getStatusText(status: StoreMySkill['status']) {
        switch (status) {
            case 'pending': return '审核中'
            case 'approved': return '已上架'
            case 'rejected': return '已拒绝'
            case 'archived': return '已归档'
            default: return status
        }
    }

    function getStatusColor(status: StoreMySkill['status']) {
        switch (status) {
            case 'pending': return 'warning'
            case 'approved': return 'success'
            case 'rejected': return 'error'
            case 'archived': return 'grey'
            default: return 'default'
        }
    }
</script>
