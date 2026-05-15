<template>
    <v-dialog :model-value="modelValue" max-width="420" @update:model-value="emit('update:modelValue', $event)">
        <v-card rounded="lg">
            <v-card-item>
                <v-card-title class="text-body-1 font-weight-bold">删除任务</v-card-title>
            </v-card-item>
            <v-card-text class="text-body-2">
                此操作无法撤销。
            </v-card-text>
            <v-card-actions class="px-5 pb-4">
                <v-spacer />
                <v-btn variant="text" rounded="lg" size="small" @click="emit('update:modelValue', false)">取消</v-btn>
                <v-btn color="error" rounded="lg" size="small" :loading="loading" @click="emit('confirm')">删除</v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script setup lang="ts">
    defineProps<{
        modelValue: boolean
        loading: boolean
    }>()

    const emit = defineEmits<{
        'update:modelValue': [value: boolean]
        confirm: []
    }>()
</script>
