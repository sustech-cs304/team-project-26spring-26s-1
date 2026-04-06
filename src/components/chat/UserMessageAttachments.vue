<template>
    <div v-if="attachments.length" class="d-flex flex-wrap justify-end ga-1 mt-1">
        <template v-for="attachment in attachments" :key="attachment.id">
            <v-avatar
                v-if="attachment.status === 'loading'"
                :color="chipColor"
                :rounded="'lg'"
                size="32"
            >
                <v-icon
                    icon="mdi-file-hidden"
                    size="16"
                    color="medium-emphasis"
                />
            </v-avatar>

            <v-img
                v-else-if="attachment.category === 'image' && getImageSrc(attachment)"
                :src="getImageSrc(attachment)"
                width="32"
                height="32"
                cover
                rounded="lg"
                class="border-thin"
            />

            <v-tooltip v-else :text="attachment.name || '附件'" location="top">
                <template #activator="{ props }">
                    <v-avatar
                        v-bind="props"
                        :color="chipColor"
                        :rounded="'lg'"
                        size="32"
                        class="cursor-help"
                    >
                        <v-icon
                            :icon="getFileIcon(attachment.category).icon"
                            :color="getFileIcon(attachment.category).color"
                            size="18"
                        />
                    </v-avatar>
                </template>
            </v-tooltip>
        </template>
    </div>
</template>

<script setup lang="ts">
    import type { UserMessageAttachment } from '@/types/attachment'
    import { getFileIcon } from '@/utils/fileUtils'
    import { useTheme } from 'vuetify'

    defineProps<{
        attachments: UserMessageAttachment[]
    }>()

    const theme = useTheme()
    const chipColor = computed(() => theme.current.value.dark ? 'grey-darken-3' : 'grey-lighten-3')

    const getImageSrc = (attachment: UserMessageAttachment) => attachment.dataUrl || attachment.previewUrl || ''
</script>
