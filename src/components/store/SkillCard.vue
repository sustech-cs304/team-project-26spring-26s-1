<template>
    <v-card class="h-100 d-flex flex-column" rounded="xl" variant="flat" border hover @click="$emit('click')">
        <div class="px-5 pt-5 pb-4 h-100 d-flex flex-column">
            <div class="d-flex align-start justify-space-between ga-3 mb-3">
               
                <v-sheet class="font-weight-bold" style="font-size: 1.3rem; line-height: 1.3;overflow: hidden;text-overflow: ellipsis;white-space: nowrap;">
                    {{ title }}
                </v-sheet>
                <slot name="top-right"></slot>
            </div>

            <v-sheet class="text-body-2 mb-4" style="font-size: 0.8rem;line-height: 1.3;overflow: hidden;text-overflow: ellipsis;min-height: 50px;;max-height:50px; color:#555;">
                {{ description || '暂无描述' }}
            </v-sheet>

            <div class="d-flex flex-wrap ga-2 mb-4 flex-grow-1 align-start">
                <v-chip v-for="(tag, index) in tags" :key="index" size="small" variant="outlined" density="comfortable" style="max-width: 100%;overflow: hidden; ">
                    {{ tag }}
                </v-chip>
            </div>

            <div class="card-meta d-flex align-center justify-space-between ga-3 mt-auto">
                <div class="meta-stat d-flex align-center ga-1">
                    <v-icon size="16">mdi-download-outline</v-icon>
                    <span>{{ formatDownloads(downloads) }}</span>
                </div>

                <div class="d-flex align-center ga-2">
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

    function formatDownloads(count: number) {
        if (count >= 1000000) return `${(count / 1000000).toFixed(1)}m`
        if (count >= 1000) return `${(count / 1000).toFixed(1)}k`
        return String(count)
    }
</script>
