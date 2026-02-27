<template>
    <div class="mb-4">
        <label class="text-body-1 mb-2 d-block">{{ label }}</label>
        <v-text-field
            v-model="model"
            :placeholder="placeholder"
            :type="type || 'text'"
            :prepend-inner-icon="icon"
            variant="outlined"
            density="default"
            color="cyan-darken-2"
            hide-details
        />
    </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
    label: string
    placeholder?: string
    type?: 'text' | 'email' | 'password'
    icon?: string
    modelValue: string
}>()

const emit = defineEmits<{
    'update:modelValue': [value: string]
}>()

const model = computed({
    get: () => props.modelValue,
    set: (value: string) => emit('update:modelValue', value)
})
</script>
