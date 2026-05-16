<template>
    <v-card class="skill-card h-100 d-flex flex-column" rounded="lg" variant="flat" border hover
        @click="$emit('click')">
        <div class="skill-card__body">
            <div class="d-flex align-center justify-space-between ga-2 mb-2">
                <div class="skill-card__title">
                    {{ title }}
                </div>
                <slot name="top-right"></slot>
            </div>

            <div class="skill-card__description">
                {{ description || '暂无描述' }}
            </div>

            <div class="skill-card__tags">
                <v-chip v-for="(tag, index) in tags.slice(0, 3)" :key="index" size="x-small" variant="outlined"
                    rounded="lg">
                    {{ tag }}
                </v-chip>
                <v-chip v-if="tags.length > 3" size="x-small" variant="tonal" rounded="lg">
                    +{{ tags.length - 3 }}
                </v-chip>
            </div>

            <div class="skill-card__footer">
                <div class="skill-card__meta">
                    <v-icon size="14">mdi-download-outline</v-icon>
                    <span>{{ formatDownloads(downloads) }}</span>
                </div>

                <div class="d-flex align-center ga-1">
                    <slot name="bottom-right"></slot>
                </div>
            </div>
        </div>
    </v-card>
</template>

<script setup lang="ts">
    defineProps<{
        title: string
        description?: string
        tags: string[]
        downloads: number
    }>()

    defineEmits(['click'])

    function formatDownloads (count: number) {
        if (count >= 1000000) return `${(count / 1000000).toFixed(1)}m`
        if (count >= 1000) return `${(count / 1000).toFixed(1)}k`
        return String(count)
    }
</script>

<style scoped>
    .skill-card {
        cursor: pointer;
        background: rgba(var(--v-theme-on-surface), 0.018) !important;
    }

    .skill-card:hover {
        background: rgba(var(--v-theme-on-surface), 0.04) !important;
    }

    .skill-card__body {
        display: flex;
        flex: 1 1 auto;
        flex-direction: column;
        min-height: 132px;
        padding: 12px 14px;
    }

    .skill-card__title {
        min-width: 0;
        overflow: hidden;
        font-size: 0.9375rem;
        font-weight: 700;
        line-height: 1.25rem;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .skill-card__description {
        display: -webkit-box;
        min-height: 34px;
        overflow: hidden;
        color: rgba(var(--v-theme-on-surface), 0.62);
        font-size: 0.8125rem;
        line-height: 1.35;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
    }

    .skill-card__tags {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 10px;
    }

    .skill-card__footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        margin-top: auto;
        padding-top: 12px;
    }

    .skill-card__meta {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        color: rgba(var(--v-theme-on-surface), 0.68);
        font-size: 0.75rem;
        font-weight: 600;
    }
</style>
