<template>
    <v-dialog :model-value="modelValue" max-width="500" @update:model-value="handleDialogChange">
        <v-card rounded="xl">
            <v-card-title class="text-h6 font-weight-bold px-6 pt-6 pb-2">上传新技能</v-card-title>

            <v-card-text class="px-6 py-4">
                <v-alert
                    v-if="validationError"
                    type="error"
                    variant="tonal"
                    density="comfortable"
                    class="mb-4"
                >
                    {{ validationError }}
                </v-alert>

                <v-file-input
                    v-model="selectedFile"
                    label="选择技能文件 (.md)"
                    accept=".md,text/markdown"
                    variant="outlined"
                    density="comfortable"
                    prepend-icon=""
                    prepend-inner-icon="mdi-language-markdown"
                    class="mb-4"
                    :rules="fileRules"
                />

                <v-select
                    v-model="selectedTagIds"
                    :items="tags"
                    item-title="name"
                    item-value="id"
                    label="选择标签 (可选)"
                    multiple
                    chips
                    variant="outlined"
                    density="comfortable"
                    hide-details
                />
            </v-card-text>

            <v-card-actions class="px-6 pb-6 pt-2">
                <v-spacer />
                <v-btn variant="text" @click="closeDialog">取消</v-btn>
                <v-btn
                    color="primary"
                    variant="flat"
                    :loading="loading || validating"
                    :disabled="!normalizedFile"
                    @click="submit"
                >
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

    function resetForm() {
        selectedFile.value = null
        selectedTagIds.value = []
        validationError.value = ''
        validating.value = false
    }

    function handleDialogChange(value: boolean) {
        emit('update:modelValue', value)
    }

    function closeDialog() {
        emit('update:modelValue', false)
    }

    async function submit() {
        if (!normalizedFile.value) return

        validationError.value = ''
        validating.value = true

        try {
            await validateSkillMarkdownFile(normalizedFile.value)
            emit('submit', {
                file: normalizedFile.value,
                tagIds: selectedTagIds.value,
            })
        } catch (error) {
            validationError.value = error instanceof Error ? error.message : '文件校验失败'
        } finally {
            validating.value = false
        }
    }
</script>
