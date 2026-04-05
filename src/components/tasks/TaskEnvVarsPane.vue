<template>
    <v-card rounded="lg" elevation="0" border min-height="680">
        <v-card-item class="px-5 pt-4 pb-2">
            <div>
                <div class="text-body-1 font-weight-bold">环境变量</div>
                <div class="text-body-large text-medium-emphasis mt-1">
                    在这里统一保存密钥值，并在任务中复用生成好的 `secret_ref`。
                </div>
            </div>
        </v-card-item>

        <v-divider />

        <v-card-text class="pa-5">
            <v-row density="compact">
                <v-col cols="12" md="5">
                    <v-card rounded="lg" elevation="0" border>
                        <v-card-item class="pb-1">
                            <v-card-title class="text-body-large font-weight-medium">创建或更新</v-card-title>
                        </v-card-item>
                        <v-card-text class="pt-2">
                            <v-text-field v-model="localKey" label="变量名" variant="outlined" rounded="lg"
                                density="compact" hide-details="auto" class="mb-3" :error="!!keyError"
                                :error-messages="keyError ? [keyError] : []" />

                            <v-textarea v-model="localValue" label="变量值" variant="outlined" rounded="lg"
                                density="compact" rows="4" auto-grow hide-details="auto" class="mb-3" />

                            <div class="d-flex justify-end">
                                <v-btn color="primary" rounded="lg" size="small" prepend-icon="mdi-content-save-outline"
                                    :loading="saving" :disabled="!localKey.trim() || !localValue.trim() || !!keyError"
                                    @click="emit('save', { key: localKey.trim(), value: localValue.trim() })">
                                    保存变量
                                </v-btn>
                            </div>
                        </v-card-text>
                    </v-card>
                </v-col>

                <v-col cols="12" md="7">
                    <v-card rounded="lg" elevation="0" border min-height="420">
                        <v-card-item class="pb-1">
                            <v-card-title class="text-body-large font-weight-medium">已保存变量</v-card-title>
                        </v-card-item>

                        <v-progress-linear v-if="loading" indeterminate />

                        <v-list v-else-if="envVars.length" nav density="compact" class="py-2">
                            <v-list-item v-for="envVar in envVars" :key="envVar.key" rounded="lg" prepend-gap="12"
                                class="mx-2 mb-1">
                                <template #prepend>
                                    <v-avatar size="24" rounded="lg" color="surface-variant">
                                        <v-icon size="14">mdi-key-variant</v-icon>
                                    </v-avatar>
                                </template>

                                <v-list-item-title class="text-body-large font-weight-medium">{{ envVar.key
                                }}</v-list-item-title>
                                <v-list-item-subtitle class="text-caption text-medium-emphasis">{{ envVar.secret_ref
                                }}</v-list-item-subtitle>

                                <template #append>
                                    <div class="d-flex align-center ga-1">
                                        <v-btn icon="mdi-content-copy" variant="text" size="x-small"
                                            @click="emit('copy', envVar.secret_ref)" />
                                        <v-btn icon="mdi-delete-outline" variant="text" size="x-small" color="error"
                                            :loading="deletingKey === envVar.key" @click="emit('delete', envVar.key)" />
                                    </div>
                                </template>
                            </v-list-item>
                        </v-list>

                        <v-empty-state v-else icon="mdi-key-outline" title="" text="还没有保存任何环境变量" />
                    </v-card>
                </v-col>
            </v-row>
        </v-card-text>
    </v-card>
</template>

<script setup lang="ts">
    import { validateEnvVarKey, type EnvVarRef } from '@/utils/tasks'
    import { ref, watch } from 'vue'

    const emit = defineEmits<{
        save: [payload: { key: string, value: string }]
        delete: [key: string]
        copy: [secretRef: string]
    }>()

    const props = defineProps<{
        envVars: EnvVarRef[]
        loading: boolean
        saving: boolean
        deletingKey: string | null
        latestSecretRef: string | null
    }>()

    const localKey = ref('')
    const localValue = ref('')
    const keyError = computed(() => {
        if (!localKey.value) return null
        return validateEnvVarKey(localKey.value)
    })

    watch(() => props.latestSecretRef, (value) => {
        if (!value) return
        localKey.value = ''
        localValue.value = ''
    })
</script>
