<template>
    <v-row density="compact" class="ga-2 flex-wrap" style="max-width: calc(9 * (60px + 8px))">
        <v-col v-for="(file, i) in files" :key="file.id" cols="auto" class="position-relative">

            <!-- 图片类型：缩略图预览 -->
            <template v-if="file.category === 'image'">
                <div class="preview-item">
                    <v-img :src="file.dataUrl" width="56" height="56" cover rounded="lg" class="border-thin" />
                    <div v-if="file.uploadStatus === 'uploading'" class="preview-mask">
                        <v-progress-circular indeterminate size="20" width="2" color="primary" />
                    </div>
                </div>
            </template>

            <!-- 非图片类型：图标卡片 -->
            <template v-else>
                <div class="preview-item">
                    <v-sheet rounded="lg" :color="cardColor" class="d-flex align-center pa-1 px-2"
                        style="width: 140px; height: 56px; overflow: hidden;">
                        <v-icon :icon="getFileIcon(file.category).icon" :color="getFileIcon(file.category).color" size="28"
                            class="flex-shrink-0" />
                        <div class="ml-2 overflow-hidden" style="min-width: 0;">
                            <div class="text-body-large text-truncate" style="line-height: 1.2;" :title="file.name">
                                {{ file.name }}
                            </div>
                            <div class="text-body-medium text-medium-emphasis" style="line-height: 1.2;">
                                {{ formatFileSize(file.size) }}
                            </div>
                        </div>
                    </v-sheet>
                    <div v-if="file.uploadStatus === 'uploading'" class="preview-mask preview-mask--wide">
                        <v-progress-circular indeterminate size="20" width="2" color="primary" />
                    </div>
                </div>
            </template>

            <!-- 关闭按钮 -->
            <v-btn icon="mdi-close" size="x-small" density="compact" variant="flat" color="surface" rounded="circle"
                class="position-absolute"
                style="top: -3px; right: -3px; width: 18px; height: 18px; min-width: 0; z-index: 1;"
                @click="remove(i)" />
        </v-col>
    </v-row>
</template>

<script setup lang="ts">
    import type { AttachmentFile } from '@/types/attachment'
    import { getFileIcon, formatFileSize } from '@/utils/fileUtils'
    import { useTheme } from 'vuetify'

    const files = defineModel<AttachmentFile[]>({ default: () => [] })

    const remove = (i: number) => {
        files.value = files.value.filter((_, idx) => idx !== i)
    }

    const theme = useTheme()
    const cardColor = computed(() => theme.current.value.dark ? 'grey-darken-3' : 'grey-lighten-3')
</script>

<style scoped>
    .preview-item {
        position: relative;
    }

    .preview-mask {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(0, 0, 0, 0.35);
        border-radius: 12px;
    }

    .preview-mask--wide {
        width: 140px;
        height: 56px;
    }
</style>
