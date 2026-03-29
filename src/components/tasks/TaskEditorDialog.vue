<template>
    <v-dialog :model-value="modelValue" max-width="1080" @update:model-value="emit('update:modelValue', $event)">
        <v-card rounded="lg" class="d-flex flex-column" style="max-height: calc(100vh - 48px);">
            <v-card-item class="px-5 pt-4">
                <v-card-title class="text-body-1 font-weight-bold">{{ title }}</v-card-title>
            </v-card-item>
            <v-card-text class="px-5 pb-5 overflow-hidden">
                <v-row density="compact" align="stretch">
                    <v-col cols="13" md="5">
                        <v-text-field v-model="form.name" label="名称" variant="solo-filled" rounded="lg" hide-details
                            class="mb-3" flat />
                        <v-textarea v-model="form.description" label="描述" variant="solo-filled" rounded="lg" rows="4"
                            auto-grow hide-details class="mb-3" flat />

                        <v-card rounded="lg" flat border class="d-flex flex-column">
                            <v-tabs v-model="activePanel" density="compact" color="primary" grow>
                                <v-tab value="schedule">调度</v-tab>
                                <v-tab value="environment">环境变量</v-tab>
                            </v-tabs>
                            <v-window v-model="activePanel" class="flex-grow-1 overflow-hidden">
                                <v-window-item value="schedule">
                                    <v-sheet color="transparent" class="pa-4">
                                        <v-text-field v-model="form.cron_expression" label="Cron 表达式"
                                            variant="solo-filled" rounded="lg" placeholder="留空则仅手动执行" hide-details
                                            flat />
                                        <div class="d-flex flex-wrap ga-2 mt-3">
                                            <v-chip v-for="preset in cronPresets" :key="preset.cron" size="small"
                                                rounded="lg" variant="outlined"
                                                @click="form.cron_expression = preset.cron">
                                                {{ preset.label }}
                                            </v-chip>
                                        </div>
                                    </v-sheet>
                                </v-window-item>

                                <v-window-item value="environment">
                                    <v-sheet color="transparent" class="pa-2 overflow-y-auto"
                                        style="max-height: 260px;">
                                        <v-list v-if="form.env_var_refs.length" bg-color="transparent" class="pa-0">
                                            <v-list-item v-for="(env, index) in form.env_var_refs" :key="index"
                                                class="px-0">
                                                <v-row class="ma-0" density="compact">
                                                    <v-col cols="5" class="pa-0">
                                                        <v-text-field v-model="env.key" placeholder="变量名"
                                                            variant="solo-filled" rounded="lg" hide-details flat
                                                            density="compact" />
                                                    </v-col>
                                                    <v-col cols="6">
                                                        <v-select v-model="env.secret_ref" :items="savedEnvVars"
                                                            item-title="key" item-value="secret_ref"
                                                            placeholder="选择 secret_ref" variant="solo-filled"
                                                            rounded="lg" hide-details flat density="compact" />
                                                    </v-col>
                                                    <v-col cols="1" class="d-flex align-center">
                                                        <v-btn icon="mdi-close" variant="text" size="x-small"
                                                            @click="emit('remove-env-var', index)" />
                                                    </v-col>
                                                </v-row>
                                            </v-list-item>
                                        </v-list>
                                        <div v-else class="text-body-small justify-center d-flex mb-3">
                                            暂无环境变量。
                                        </div>
                                        <div class="d-flex justify-end mb-3">
                                            <v-btn variant="text" rounded="lg" size="small" prepend-icon="mdi-plus"
                                                @click="emit('add-env-var')">
                                                添加变量
                                            </v-btn>
                                        </div>
                                    </v-sheet>
                                </v-window-item>
                            </v-window>
                        </v-card>
                    </v-col>

                    <v-col cols="12" md="7" class="d-flex">
                        <v-card rounded="lg" elevation="0" class="d-flex flex-column flex-grow-1 overflow-hidden w-100">
                            <v-card-item>
                                <div class="d-flex align-center justify-space-between ga-3 flex-wrap">
                                    <div class="d-flex align-center ga-2">
                                        <v-icon>{{ MODE_ICON[form.execution_mode] }}</v-icon>
                                        <span class="font-weight-medium">{{ MODE_LABEL[form.execution_mode] }}</span>
                                    </div>
                                    <v-chip size="small" variant="tonal">{{ form.execution_mode }}</v-chip>
                                </div>
                            </v-card-item>
                            <div class="flex-grow-1" style="min-height: 410px;">
                                <MonacoEditor v-model="form.payload"
                                    :language="form.execution_mode === 'script' ? 'python' : 'markdown'"
                                    :show-line-numbers="form.execution_mode === 'script'" />
                            </div>
                        </v-card>
                    </v-col>
                </v-row>
            </v-card-text>
            <v-card-actions class="px-5 pb-4">
                <v-spacer />
                <v-btn variant="text" rounded="lg" size="small" @click="emit('update:modelValue', false)">取消</v-btn>
                <v-btn color="primary" rounded="lg" size="small" :loading="saving" :disabled="!form.name.trim()"
                    @click="emit('save')">
                    {{ actionLabel }}
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script setup lang="ts">
    import MonacoEditor from '@/components/editor/MonacoEditor.vue'
    import { MODE_ICON, MODE_LABEL, type EnvVarRef, type Task } from '@/utils/tasks'

    interface EditorForm {
        name: string
        description: string
        execution_mode: Task['execution_mode']
        payload: string
        cron_expression: string
        env_var_refs: EnvVarRef[]
    }

    defineProps<{
        modelValue: boolean
        title: string
        actionLabel: string
        saving: boolean
        form: EditorForm
        cronPresets: { label: string, cron: string }[]
        savedEnvVars: EnvVarRef[]
    }>()

    const emit = defineEmits<{
        'update:modelValue': [value: boolean]
        'add-env-var': []
        'remove-env-var': [index: number]
        save: []
    }>()

    const activePanel = ref<'schedule' | 'environment'>('schedule')
</script>
