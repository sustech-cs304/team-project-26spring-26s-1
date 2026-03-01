<template>
    <div class="w-100">
        <v-textarea :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)"
            placeholder="输入消息…" variant="outlined" rounded="lg" rows="3" auto-grow max-rows="8" hide-details
            class="w-100" @keydown.enter.exact.prevent="send">
            <template #append-inner>
                <v-btn icon="mdi-send" size="small" :color="modelValue.trim() ? 'primary' : undefined"
                    :disabled="!modelValue.trim()" variant="text" :ripple="false" @click="send" />
            </template>
        </v-textarea>
        <v-card-subtitle class="pa-0 mt-2">按 Enter 发送 · Shift+Enter 换行</v-card-subtitle>
    </div>
</template>

<script setup lang="ts">
    const props = defineProps<{
        modelValue: string
    }>()

    const emit = defineEmits<{
        (e: 'update:modelValue', value: string): void
        (e: 'send'): void
    }>()

    const send = () => {
        if (!props.modelValue.trim()) return
        emit('send')
    }
</script>
