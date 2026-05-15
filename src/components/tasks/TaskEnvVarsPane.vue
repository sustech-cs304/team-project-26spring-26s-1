<template>
    <v-card rounded="0" elevation="0" color="transparent" class="h-100 d-flex flex-column overflow-hidden">
        <v-card-item class="px-5 py-0 flex-shrink-0">
            <div class="d-flex align-center justify-space-between ga-3">
                <div class="text-subtitle-2 font-weight-bold">环境变量</div>
                <v-chip size="x-small" variant="tonal" rounded="lg">
                    {{ envVars.length }} 个
                </v-chip>
            </div>
        </v-card-item>

        <v-card-text class="d-flex flex-column flex-grow-1 overflow-hidden min-height-0 px-5 pt-2 pb-4">
            <v-card rounded="lg" variant="flat" border color="transparent" class="flex-shrink-0">
                <v-card-text class="pa-3">
                    <div class="text-body-2 font-weight-bold mb-2">新增或更新</div>

                    <v-row dense align="center">
                        <v-col cols="12" md="4" class="d-flex align-center ga-2">
                            <v-text-field v-model="localKey" placeholder="变量名" variant="solo-filled" flat rounded="lg"
                                density="compact" hide-details="auto" :error="!!keyError"
                                :error-messages="keyError ? [keyError] : []" />
                        </v-col>

                        <v-col cols="12" md="4" class="d-flex align-center ga-2">
                            <v-text-field v-model="localValue" placeholder="变量值" variant="solo-filled" flat rounded="lg"
                                density="compact" type="password" hide-details="auto" />
                        </v-col>

                        <v-col cols="12" md="auto" class="d-flex">
                            <v-btn variant="tonal" rounded="lg" prepend-icon="mdi-content-save-outline"
                                :loading="saving" :disabled="!localKey.trim() || !localValue.trim() || !!keyError"
                                @click="emit('save', { key: localKey.trim(), value: localValue.trim() })">
                                保存
                            </v-btn>
                        </v-col>
                    </v-row>

                    <div class="text-caption text-medium-emphasis mt-1">
                        同名保存会覆盖旧值。点击下方变量名可带入编辑。
                    </div>
                </v-card-text>
            </v-card>

            <v-card rounded="lg" variant="flat" border color="transparent"
                class="mt-2 flex-grow-1 d-flex flex-column overflow-hidden min-height-0">
                <div class="d-flex align-center justify-space-between px-3 py-2">
                    <div class="text-body-2 font-weight-bold">已保存变量</div>
                    <v-progress-circular v-if="loading" indeterminate size="16" width="2" />
                </div>

                <v-divider />

                <v-card-text class="pa-0 flex-grow-1 overflow-y-auto min-height-0">
                    <v-list v-if="!loading && envVars.length" bg-color="transparent" density="compact" nav slim
                        class="pa-1">
                        <v-list-item v-for="envVar in envVars" :key="envVar.key" rounded="lg" slim
                            prepend-icon="mdi-key-outline" :title="envVar.key" :ripple="false" class="px-2 my-1"
                            @click="localKey = envVar.key">
                            <template #append>
                                <div class="d-flex align-center ga-1">
                                    <v-btn variant="text" size="small" density="comfortable" icon="mdi-content-copy"
                                        aria-label="复制变量名" @click.stop="copyEnvVarKey(envVar.key)" />
                                    <v-btn variant="text" size="small" density="comfortable" icon="mdi-delete-outline"
                                        aria-label="删除变量" :loading="deletingKey === envVar.key"
                                        @click.stop="emit('delete', envVar.key)" />
                                </div>
                            </template>
                        </v-list-item>
                    </v-list>

                    <div v-else-if="!loading" class="h-100 d-flex align-center justify-center px-4">
                        <span class="text-body-2 text-medium-emphasis">还没有保存任何环境变量</span>
                    </div>
                </v-card-text>
            </v-card>
        </v-card-text>
    </v-card>
</template>

<script setup lang="ts">
    import { copyText } from '@/utils/copyText'
    import { validateEnvVarKey, type EnvVarRef } from '@/utils/tasks'
    import { ref, watch } from 'vue'

    const emit = defineEmits<{
        save: [payload: { key: string, value: string }]
        delete: [key: string]
    }>()

    const props = defineProps<{
        envVars: EnvVarRef[]
        loading: boolean
        saving: boolean
        deletingKey: string | null
        latestSavedKey: string | null
    }>()

    const localKey = ref('')
    const localValue = ref('')
    const keyError = computed(() => {
        if (!localKey.value) return null
        return validateEnvVarKey(localKey.value)
    })

    watch(() => props.latestSavedKey, (value) => {
        if (!value) return
        localKey.value = ''
        localValue.value = ''
    })

    async function copyEnvVarKey (key: string) {
        await copyText(key)
    }
</script>
