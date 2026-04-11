<template>
    <div class="w-100">
        <v-sheet rounded="xl" color="surface" elevation="1" class="px-4  pb-2" style="cursor: text;"
            @click="focusTextarea">
            <FilePreview v-if="attachments.length" v-model="attachments" class="pt-4 pb-0" />
            <v-textarea ref="textareaRef" :model-value="modelValue"
                @update:model-value="emit('update:modelValue', $event)" :placeholder="disabled ? '请先处理待审批的操作…' : '发送消息（Ctrl + Enter）'" variant="plain"
                rows="1" auto-grow max-rows="6" hide-details :disabled="disabled" @keydown.ctrl.enter.exact.prevent="send" @paste="onPaste">
            </v-textarea>
            <!-- Toolbar -->
            <v-row align="center" density="compact" class="mt-1">
                <!-- 左侧：上传文件 -->
                <v-btn icon="mdi-plus" size="small" variant="text" :ripple="false" :disabled="loading || disabled"
                    @click="triggerUpload" />
                <input ref="fileInput" type="file" :accept="ACCEPT_STRING" multiple class="d-none"
                    @change="onFileChange" />
                <v-spacer />
                <v-scale-transition mode="out-in">
                    <v-btn v-if="loading" key="stop" icon="mdi-stop" size="small" color="primary" variant="tonal"
                        :ripple="false" @click="$emit('stop')" />
                    <v-btn v-else-if="asr.isStarting.value" key="starting" icon="mdi-loading" size="small" color="warning"
                        variant="tonal" :ripple="false" :loading="true" disabled />
                    <v-btn v-else-if="!hasContent && !asr.isRecording.value" key="mic" icon="mdi-microphone-outline"
                        size="small" variant="text" :ripple="false" :disabled="disabled" @click="toggleRecording" />
                    <v-btn v-else-if="asr.isRecording.value" key="recording" icon="mdi-microphone" size="small"
                        color="error" variant="flat" :ripple="false" @click="toggleRecording" />
                    <v-btn v-else key="send" icon="mdi-send" size="small" variant="flat" :ripple="false"
                        :disabled="!canSend" @click="send" />
                </v-scale-transition>
            </v-row>
        </v-sheet>

        <!-- 错误提示 Snackbar -->
        <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="4000" location="top">
            {{ snackbar.text }}
            <template #actions>
                <v-btn variant="text" @click="snackbar.show = false">关闭</v-btn>
            </template>
        </v-snackbar>
    </div>
</template>

<script setup lang="ts">
    import { uploadFile } from '@/api/file'
    import FilePreview from '@/components/chat/FilePreview.vue'
    import type { AttachmentFile } from '@/types/attachment'
    import {
        ACCEPT_STRING,
        validateFile,
        getFileCategory,
        computeFileMd5,
        generateFileId,
    } from '@/utils/fileUtils'
    import { useAsr } from '@/composables/useAsr'

    const props = defineProps<{
        modelValue: string
        loading?: boolean
        disabled?: boolean
    }>()

    const emit = defineEmits<{
        (e: 'update:modelValue', value: string): void
        (e: 'send'): void
        (e: 'stop'): void
    }>()

    // ── 附件状态 ──────────────────────────
    const attachments = ref<AttachmentFile[]>([])
    const fileInput = ref<HTMLInputElement | null>(null)
    const textareaRef = ref<{ $el: HTMLElement } | null>(null)

    // ── Snackbar ─────────────────────────
    const snackbar = reactive({
        show: false,
        text: '',
        color: 'error',
    })

    const showError = (msg: string) => {
        snackbar.text = msg
        snackbar.color = 'error'
        snackbar.show = true
    }

    const showWarning = (msg: string) => {
        snackbar.text = msg
        snackbar.color = 'warning'
        snackbar.show = true
    }

    // ── ASR 语音识别 ─────────────────────
    const asr = useAsr({
        onTranscript: (text: string) => {
            emit('update:modelValue', text)
        },
        onError: (message: string) => {
            showError(message)
        },
    })

    // ── 基本交互 ─────────────────────────
    const focusTextarea = (e: MouseEvent) => {
        const target = e.target as HTMLElement
        if (target.closest('button, input, a, [role="button"]')) return
        const textarea = textareaRef.value?.$el?.querySelector('textarea')
        textarea?.focus()
    }

    const hasContent = computed(() =>
        !!(props.modelValue.trim() || attachments.value.length > 0)
    )

    const hasUploadingAttachments = computed(() =>
        attachments.value.some(file => file.uploadStatus === 'uploading')
    )

    const canSend = computed(() =>
        hasContent.value && !props.loading && !props.disabled && !hasUploadingAttachments.value
    )

    const toggleRecording = () => {
        if (asr.isStarting.value || asr.isRecording.value) {
            asr.stopRecording()
        } else {
            asr.startRecording()
        }
    }

    const triggerUpload = () => {
        fileInput.value?.click()
    }

    // ── 核心：处理文件添加 ───────────────────
    /**
     * 处理一组文件：校验 → MD5 计算 → 去重 → 添加到 attachments
     * 供 onFileChange、onPaste、以及父组件拖拽调用
     */
    const updateAttachment = (attachmentId: string, updater: (attachment: AttachmentFile) => AttachmentFile) => {
        attachments.value = attachments.value.map((attachment) =>
            attachment.id === attachmentId ? updater(attachment) : attachment
        )
    }

    const removeAttachment = (attachmentId: string) => {
        attachments.value = attachments.value.filter(attachment => attachment.id !== attachmentId)
    }

    const addFiles = async (files: FileList | File[]) => {
        for (const file of files) {
            // 1. 校验类型和大小
            const validation = validateFile(file)
            if (!validation.valid) {
                showError(validation.error!)
                continue
            }

            // 2. 计算 MD5
            let md5: string
            try {
                md5 = await computeFileMd5(file)
            } catch {
                showError(`文件 "${file.name}" 读取失败`)
                continue
            }

            // 3. 重复检测
            if (attachments.value.some(a => a.md5 === md5)) {
                showWarning(`文件 "${file.name}" 已添加，请勿重复上传`)
                continue
            }

            // 4. 读取为 data URL
            const dataUrl = await readFileAsDataUrl(file)
            if (!dataUrl) {
                showError(`文件 "${file.name}" 读取失败`)
                continue
            }

            // 5. 构建 AttachmentFile 并添加
            const category = getFileCategory(file)!
            const attachmentId = generateFileId()
            const attachment: AttachmentFile = {
                id: attachmentId,
                name: file.name,
                size: file.size,
                type: file.type,
                category,
                dataUrl,
                md5,
                uploadStatus: 'uploading',
            }
            attachments.value = [...attachments.value, attachment]

            // 6. 真正上传到后端，成功后写入 file_id
            try {
                const uploaded = await uploadFile(file)
                updateAttachment(attachmentId, current => ({
                    ...current,
                    fileId: uploaded.file_id,
                    type: uploaded.mime_type || current.type,
                    uploadStatus: 'ready',
                }))
            } catch {
                removeAttachment(attachmentId)
                showError(`文件 "${file.name}" 上传失败，请重试`)
            }
        }
    }

    /** 将 File 读取为 base64 data URL */
    const readFileAsDataUrl = (file: File): Promise<string | null> => {
        return new Promise((resolve) => {
            const reader = new FileReader()
            reader.onload = (ev) => {
                const result = ev.target?.result
                resolve(typeof result === 'string' ? result : null)
            }
            reader.onerror = () => resolve(null)
            reader.readAsDataURL(file)
        })
    }

    // ── 事件处理 ─────────────────────────
    const onFileChange = async (e: Event) => {
        const files = (e.target as HTMLInputElement).files
        if (!files || files.length === 0) return
        await addFiles(files)
        // 清空 input 以允许重复选同一文件
        if (fileInput.value) fileInput.value.value = ''
    }

    const onPaste = async (e: ClipboardEvent) => {
        const items = e.clipboardData?.items
        if (!items) return
        const files: File[] = []
        for (const item of items) {
            // 支持所有允许的类型（不仅仅是图片）
            const file = item.getAsFile()
            if (file) {
                files.push(file)
            }
        }
        if (files.length > 0) {
            await addFiles(files)
        }
    }

    const send = () => {
        if (!canSend.value) return
        emit('send')
    }

    // ── 暴露给父组件（用于拖拽上传） ──────────
    const getAttachmentsSnapshot = (): AttachmentFile[] =>
        attachments.value.map(file => ({ ...file }))

    const clearAttachments = () => {
        attachments.value = []
    }

    defineExpose({ addFiles, getAttachmentsSnapshot, clearAttachments })
</script>
