<template>
    <v-dialog :model-value="modelValue" max-width="520" @update:model-value="handleDialogChange">
        <v-card rounded="lg" class="upload-skill-dialog">
            <div class="upload-skill-header">
                <div>
                    <div class="text-subtitle-1 font-weight-bold">上传技能</div>
                    <div class="text-caption text-medium-emphasis">提交 Markdown 技能文件，审核后进入商店。</div>
                </div>
                <v-btn icon="mdi-close" size="small" variant="text" :ripple="false" @click="closeDialog" />
            </div>

            <v-card-text class="upload-skill-body">
                <v-alert v-if="validationError" type="error" variant="tonal" density="compact" rounded="lg"
                    class="mb-3">
                    {{ validationError }}
                </v-alert>

                <div class="upload-field">
                    <div class="upload-field__label">文件</div>
                    <v-file-input v-model="selectedFile" placeholder="选择 .md 文件" accept=".md,text/markdown"
                        variant="solo-filled" flat density="compact" prepend-icon=""
                        prepend-inner-icon="mdi-language-markdown" rounded="lg" hide-details="auto"
                        :rules="fileRules" />
                </div>

                <div class="upload-field">
                    <div class="upload-field__label">标签</div>
                    <v-select v-model="selectedTagIds" :items="tags" item-title="name" item-value="id"
                        placeholder="可选，最多 3 个" multiple chips variant="solo-filled" flat density="compact"
                        rounded="lg" hide-details />
                </div>
            </v-card-text>

            <v-card-actions class="upload-skill-actions">
                <v-spacer />
                <v-btn size="small" variant="text" @click="closeDialog">取消</v-btn>
                <v-btn size="small" variant="tonal" prepend-icon="mdi-upload-outline" :loading="loading || validating"
                    :disabled="!normalizedFile" @click="submit">
                    提交审核
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script setup lang="ts">
    import { computed, ref, watch } from 'vue'
    import type { StoreTag } from '@/types/store'
    import { validateSkillMarkdownFile } from '@/utils/skillUpload'

    const props = defineProps<{
        modelValue: boolean
        loading: boolean
        tags: StoreTag[]
    }>()

    const emit = defineEmits<{
        'update:modelValue': [value: boolean]
        submit: [payload: { file: File, tagIds: number[] }]
    }>()

    const selectedFile = ref<File | File[] | null>(null)
    const selectedTagIds = ref<number[]>([])
    const validationError = ref('')
    const validating = ref(false)
    const MAX_SELECTED_TAGS = 3

    const normalizedFile = computed(() => {
        const file = Array.isArray(selectedFile.value) ? selectedFile.value[0] : selectedFile.value
        return file ?? null
    })

    const fileRules = [
        (value: File | File[] | null) => {
            const file = Array.isArray(value) ? value[0] : value
            if (!file) return '请选择一个 Markdown 技能文件'

            const fileName = file.name.toLowerCase()
            const isMarkdown = fileName.endsWith('.md') || file.type === 'text/markdown'
            return isMarkdown || '仅支持上传 .md 文件'
        },
    ]

    watch(() => props.modelValue, (isOpen) => {
        if (!isOpen) {
            resetForm()
        }
    })

    watch(normalizedFile, () => {
        validationError.value = ''
    })

    watch(selectedTagIds, (tagIds) => {
        if (tagIds.length > MAX_SELECTED_TAGS) {
            selectedTagIds.value = tagIds.slice(0, MAX_SELECTED_TAGS)
        }
    })

    function resetForm () {
        selectedFile.value = null
        selectedTagIds.value = []
        validationError.value = ''
        validating.value = false
    }

    function handleDialogChange (value: boolean) {
        emit('update:modelValue', value)
    }

    function closeDialog () {
        emit('update:modelValue', false)
    }

    async function submit () {
        if (!normalizedFile.value) return

        validationError.value = ''
        validating.value = true

        try {
            await validateSkillMarkdownFile(normalizedFile.value)
            emit('submit', {
                file: normalizedFile.value,
                tagIds: selectedTagIds.value.slice(0, MAX_SELECTED_TAGS),
            })
        } catch (error) {
            validationError.value = error instanceof Error ? error.message : '文件校验失败'
        } finally {
            validating.value = false
        }
    }
</script>

<style scoped>
    .upload-skill-dialog {
        overflow: hidden;
        border: 1px solid rgba(var(--v-border-color), 0.16);
    }

    .upload-skill-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 12px 14px;
        border-bottom: 1px solid rgba(var(--v-border-color), 0.14);
    }

    .upload-skill-body {
        display: grid;
        gap: 12px;
        padding: 12px 14px;
    }

    .upload-field {
        display: grid;
        grid-template-columns: 56px minmax(0, 1fr);
        align-items: start;
        gap: 10px;
    }

    .upload-field__label {
        padding-top: 7px;
        color: rgba(var(--v-theme-on-surface), 0.62);
        font-size: 0.8125rem;
    }

    .upload-skill-actions {
        padding: 8px 14px 12px;
        border-top: 1px solid rgba(var(--v-border-color), 0.14);
    }
</style>
