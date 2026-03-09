<template>
    <div class="w-100">
        <v-sheet rounded="xl" color="surface" elevation="1" class="px-4  pb-2" style="cursor: text;"
            @click="focusTextarea">
            <ImagePreview v-if="images.length" v-model="images" class="pt-4 pb-0" />
            <v-textarea ref="textareaRef" :model-value="modelValue"
                @update:model-value="emit('update:modelValue', $event)" placeholder="发送消息，或输入 / 使用命令…" variant="plain"
                rows="1" auto-grow max-rows="6" hide-details @keydown.enter.exact.prevent="send" @paste="onPaste">
            </v-textarea>
            <!-- Toolbar -->
            <v-row align="center" density="compact" class="mt-1">
                <!-- 左侧：上传文件 -->
                <v-btn icon="mdi-plus" size="small" variant="text" :ripple="false" :disabled="loading"
                    @click="triggerUpload" />
                <input ref="fileInput" type="file" accept="image/*" multiple class="d-none" @change="onFileChange" />
                <v-spacer />
                <v-scale-transition mode="out-in">
                    <v-btn v-if="loading" key="stop" icon="mdi-stop" size="small" color="primary" variant="tonal"
                        :ripple="false" @click="$emit('stop')" />
                    <v-btn v-else-if="!hasContent && !isRecording" key="mic" icon="mdi-microphone-outline" size="small"
                        variant="text" :ripple="false" @click="toggleRecording" />
                    <v-btn v-else-if="isRecording" key="recording" icon="mdi-microphone" size="small" color="error"
                        variant="flat" :ripple="false" @click="toggleRecording" />
                    <v-btn v-else key="send" icon="mdi-send" size="small" variant="flat" :ripple="false"
                        @click="send" />
                </v-scale-transition>
            </v-row>
        </v-sheet>
    </div>
</template>

<script setup lang="ts">
    import ImagePreview from '@/components/chat/ImagePreview.vue'

    const props = defineProps<{
        modelValue: string
        loading?: boolean
    }>()

    const emit = defineEmits<{
        (e: 'update:modelValue', value: string): void
        (e: 'send'): void
        (e: 'stop'): void
    }>()

    const images = ref<string[]>([])
    const fileInput = ref<HTMLInputElement | null>(null)
    const textareaRef = ref<{ $el: HTMLElement } | null>(null)

    const focusTextarea = (e: MouseEvent) => {
        const target = e.target as HTMLElement
        if (target.closest('button, input, a, [role="button"]')) return
        const textarea = textareaRef.value?.$el?.querySelector('textarea')
        textarea?.focus()
    }

    const hasContent = computed(() =>
        !!(props.modelValue.trim() || images.value.length > 0)
    )

    const canSend = computed(() => hasContent.value && !props.loading)

    const isRecording = ref(false)

    const toggleRecording = () => {
        isRecording.value = !isRecording.value
    }

    const triggerUpload = () => {
        fileInput.value?.click()
    }

    const onFileChange = (e: Event) => {
        const files = (e.target as HTMLInputElement).files
        if (!files) return
        for (const file of files) {
            if (!file.type.startsWith('image/')) continue
            const reader = new FileReader()
            reader.onload = (ev) => {
                const result = ev.target?.result
                if (typeof result === 'string') {
                    images.value = [...images.value, result]
                }
            }
            reader.readAsDataURL(file)
        }
        // 清空 input 以允许重复选同一文件
        if (fileInput.value) fileInput.value.value = ''
    }

    const onPaste = (e: ClipboardEvent) => {
        const items = e.clipboardData?.items
        if (!items) return
        for (const item of items) {
            if (item.type.startsWith('image/')) {
                const file = item.getAsFile()
                if (!file) continue
                const reader = new FileReader()
                reader.onload = (ev) => {
                    const result = ev.target?.result
                    if (typeof result === 'string') {
                        images.value = [...images.value, result]
                    }
                }
                reader.readAsDataURL(file)
            }
        }
    }

    const send = () => {
        if (!canSend.value) return
        emit('send')
    }
</script>
