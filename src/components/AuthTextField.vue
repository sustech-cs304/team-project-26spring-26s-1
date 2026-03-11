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
                :rules="rules"
                type="text"
                :error-messages="errorMessages"
                :autocomplete="isPassword ? 'new-password' : undefined"
                :class="{ 'password-field': isPassword && !showPassword }"
                variant="outlined"
                density="default"
                color="cyan-darken-2"
                class="flex-grow-1"
            >
                <template #append-inner v-if="isPassword">
                    <v-icon 
                        :icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'" 
                        @click="showPassword = !showPassword"
                        style="cursor: pointer;"
                    />
                </template>
            </v-text-field>
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
}>(), {
    rules: () => [],
    isPassword: false,
    errorMessages: () => []
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

<style scoped>
.password-field :deep(input) {
    -webkit-text-security: disc;
}
</style>