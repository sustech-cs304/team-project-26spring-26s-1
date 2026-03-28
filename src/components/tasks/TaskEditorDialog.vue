<template>
    <v-dialog :model-value="modelValue" max-width="1080" @update:model-value="emit('update:modelValue', $event)">
        <v-card rounded="lg">
            <v-card-item class="px-5 pt-4">
                <v-card-title class="text-body-1 font-weight-bold">{{ title }}</v-card-title>
            </v-card-item>
            <v-card-text class="px-5 pb-5">
                <v-row density="compact">
                    <v-col cols="12" md="4">
                        <v-text-field
                            v-model="form.name"
                            label="Name"
                            variant="outlined"
                            rounded="lg"
                            density="compact"
                            hide-details="auto"
                            class="mb-3 task-edit-field"
                        />
                        <v-textarea
                            v-model="form.description"
                            label="Description"
                            variant="outlined"
                            rounded="lg"
                            density="compact"
                            rows="4"
                            auto-grow
                            hide-details="auto"
                            class="mb-3 task-edit-field"
                        />

                        <v-expansion-panels variant="accordion">
                            <v-expansion-panel rounded="lg">
                                <v-expansion-panel-title>Schedule</v-expansion-panel-title>
                                <v-expansion-panel-text>
                                    <v-text-field
                                        v-model="form.cron_expression"
                                        label="Cron expression"
                                        variant="outlined"
                                        rounded="lg"
                                        density="compact"
                                        placeholder="Leave empty for manual only"
                                        hide-details="auto"
                                    />
                                    <div class="d-flex flex-wrap ga-2 mt-3">
                                        <v-chip
                                            v-for="preset in cronPresets"
                                            :key="preset.cron"
                                            size="small"
                                            rounded="lg"
                                            variant="outlined"
                                            @click="form.cron_expression = preset.cron"
                                        >
                                            {{ preset.label }}
                                        </v-chip>
                                    </div>
                                </v-expansion-panel-text>
                            </v-expansion-panel>

                            <v-expansion-panel rounded="lg">
                                <v-expansion-panel-title>Environment variables</v-expansion-panel-title>
                                <v-expansion-panel-text>
                                    <div class="d-flex justify-end mb-3">
                                        <v-btn variant="text" rounded="lg" size="small" prepend-icon="mdi-plus" @click="emit('add-env-var')">
                                            Add variable
                                        </v-btn>
                                    </div>
                                    <v-list v-if="form.env_var_refs.length" bg-color="transparent" class="pa-0 overflow-visible">
                                        <v-list-item
                                            v-for="(env, index) in form.env_var_refs"
                                            :key="`${index}-${env.key}`"
                                            class="px-0 task-env-item"
                                        >
                                            <v-row class="ma-0" density="comfortable">
                                                <v-col cols="5" class="pa-0 pr-1">
                                                    <v-text-field
                                                        v-model="env.key"
                                                        label="Key"
                                                        variant="outlined"
                                                        rounded="lg"
                                                        density="comfortable"
                                                        hide-details
                                                        class="task-edit-field task-env-field"
                                                    />
                                                </v-col>
                                                <v-col cols="6" class="pa-0 pr-1">
                                                    <v-text-field
                                                        v-model="env.secret_ref"
                                                        label="Secret ref"
                                                        variant="outlined"
                                                        rounded="lg"
                                                        density="comfortable"
                                                        hide-details
                                                        class="task-edit-field task-env-field"
                                                    />
                                                </v-col>
                                                <v-col cols="1" class="pa-0 d-flex align-center">
                                                    <v-btn icon="mdi-close" variant="text" size="small" @click="emit('remove-env-var', index)" />
                                                </v-col>
                                            </v-row>
                                        </v-list-item>
                                    </v-list>
                                    <div v-else class="text-medium-emphasis">No environment variables.</div>
                                </v-expansion-panel-text>
                            </v-expansion-panel>
                        </v-expansion-panels>
                    </v-col>

                    <v-col cols="12" md="8">
                        <v-card rounded="lg" elevation="0" border class="overflow-hidden">
                            <v-card-item>
                                <div class="d-flex align-center justify-space-between ga-3 flex-wrap">
                                    <div class="d-flex align-center ga-2">
                                        <v-icon>{{ MODE_ICON[form.execution_mode] }}</v-icon>
                                        <span class="font-weight-medium">{{ MODE_LABEL[form.execution_mode] }}</span>
                                    </div>
                                    <v-chip size="small" variant="tonal">{{ form.execution_mode }}</v-chip>
                                </div>
                            </v-card-item>
                            <v-divider />
                            <div class="task-editor-preview">
                                <MonacoEditor
                                    v-model="form.payload"
                                    :language="form.execution_mode === 'script' ? 'python' : 'markdown'"
                                    :show-line-numbers="form.execution_mode === 'script'"
                                />
                            </div>
                        </v-card>
                    </v-col>
                </v-row>
            </v-card-text>
            <v-card-actions class="px-5 pb-4">
                <v-spacer />
                <v-btn variant="text" rounded="lg" size="small" @click="emit('update:modelValue', false)">Cancel</v-btn>
                <v-btn
                    color="primary"
                    rounded="lg"
                    size="small"
                    :loading="saving"
                    :disabled="!form.name.trim()"
                    @click="emit('save')"
                >
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
    }>()

    const emit = defineEmits<{
        'update:modelValue': [value: boolean]
        'add-env-var': []
        'remove-env-var': [index: number]
        save: []
    }>()
</script>

<style scoped>
    .task-edit-field :deep(.v-field) {
        background: transparent;
    }

    .task-env-item {
        padding-block: 4px;
        overflow: visible;
    }

    .task-env-field :deep(.v-field) {
        min-height: 48px;
    }

    .task-env-item :deep(.v-list-item__content),
    .task-env-item :deep(.v-list-item__append),
    .task-env-field :deep(.v-input__control),
    .task-env-field :deep(.v-field__field) {
        overflow: visible;
    }

    .task-edit-field :deep(.v-label),
    .task-edit-field :deep(input),
    .task-edit-field :deep(textarea) {
        font-size: 0.92rem;
    }

    .task-editor-preview {
        height: 400px;
    }
</style>
