<template>
    <div class="mb-4">
        <div class="d-flex justify-space-between align-center mb-2">
            <label class="text-body-1">{{ label }}</label>
            <slot name="label-append"></slot>
        </div>
        <div class="d-flex align-start ga-2">
           <v-text-field
                v-model="model"
                :placeholder="placeholder"
                :prepend-inner-icon="icon"
                :append-inner-icon="isPassword ? (showPassword ? 'mdi-eye' : 'mdi-eye-off') : undefined"
                :rules="rules"
                :type="isPassword ? (showPassword ? 'text' : 'password') : 'text'"
                :error-messages="errorMessages"
                @click:append-inner="isPassword && (showPassword = !showPassword)"
                variant="outlined"
                :density="props.compact ? 'compact' : 'default'"
                color="cyan-darken-2"
                class="flex-grow-1"
            />
            <slot name="append"></slot>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const props = withDefaults(defineProps<{
    label: string
    placeholder?: string
    icon?: string
    modelValue: string
    rules?: ((v: string) => boolean | string)[]
    isPassword?: boolean
    errorMessages?: string | string[]
    compact?: boolean
}>(), {
    rules: () => [],
    isPassword: false,
    errorMessages: () => [],
    compact: false,
})

const emit = defineEmits<{
    'update:modelValue': [value: string]
}>()

const showPassword = ref(false)

const model = computed({
    get: () => props.modelValue,
    set: (value: string) => emit('update:modelValue', value)
})
</script>

<style>
    input::-ms-reveal {
        display: none !important;
    }
</style>
