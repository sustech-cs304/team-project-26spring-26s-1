<template>
    <v-dialog :model-value="modelValue" max-width="960" @update:model-value="emit('update:modelValue', $event)">
        <v-card rounded="lg" color="surface" class="task-editor-card overflow-hidden d-flex flex-column">
            <div class="d-flex align-center justify-space-between ga-3 px-4 py-2 flex-shrink-0">
                <div>
                    <div class="text-subtitle-2 font-weight-bold">{{ title }}</div>
                </div>
                <v-btn icon="mdi-close" variant="text" size="small" aria-label="关闭"
                    @click="emit('update:modelValue', false)" />
            </div>

            <v-divider />

            <v-card-text class="task-editor-body pa-0">
                <div class="task-editor-layout">
                    <aside class="task-editor-sidebar border-e">
                        <div class="task-editor-sidebar-inner">
                            <div class="task-editor-panel">
                                <div class="task-editor-section-title">
                                    <v-icon size="15">mdi-form-textbox</v-icon>
                                    <span>任务信息</span>
                                </div>

                                <label class="task-field-label">名称</label>
                                <v-text-field v-model="form.name" placeholder="任务名称" variant="solo-filled" flat
                                    density="compact" rounded="lg" hide-details class="task-editor-field" />

                                <label class="task-field-label mt-2">描述</label>
                                <v-textarea v-model="form.description" placeholder="补充任务用途" variant="solo-filled" flat
                                    density="compact" rounded="lg" rows="2" hide-details
                                    class="task-editor-field task-editor-textarea" />
                            </div>

                            <div class="task-editor-panel">
                                <div class="task-editor-section-title">
                                    <v-icon size="15">mdi-code-tags</v-icon>
                                    <span>内容类型</span>
                                </div>
                                <v-btn-toggle v-model="form.execution_mode" mandatory density="compact" variant="tonal"
                                    rounded="lg" divided class="task-editor-toggle w-100">
                                    <v-btn value="script" size="x-small" class="text-none flex-grow-1">
                                        <v-icon start size="14">{{ MODE_ICON.script }}</v-icon>
                                        {{ MODE_LABEL.script }}
                                    </v-btn>
                                    <v-btn value="prompt" size="x-small" class="text-none flex-grow-1">
                                        <v-icon start size="14">{{ MODE_ICON.prompt }}</v-icon>
                                        提示词
                                    </v-btn>
                                </v-btn-toggle>
                            </div>

                            <div class="task-editor-panel">
                                <div class="task-editor-section-title">
                                    <v-icon size="15">mdi-tune-variant</v-icon>
                                    <span>运行调度</span>
                                </div>

                                <v-text-field v-model="form.cron_expression" variant="solo-filled" flat
                                    density="compact" rounded="lg" placeholder="留空则仅手动执行" hide-details="auto"
                                    :error="!!cronError" :error-messages="cronError ? [cronError] : []"
                                    class="task-editor-field" />
                                <div class="task-preset-grid mt-1">
                                    <v-btn v-for="preset in cronPresets" :key="preset.cron" size="x-small" rounded="lg"
                                        variant="tonal" class="text-none" @click="form.cron_expression = preset.cron">
                                        {{ preset.label }}
                                    </v-btn>
                                </div>
                            </div>

                            <div v-if="form.execution_mode === 'script'" class="task-env-inline">
                                <div class="task-env-inline-header">
                                    <span class="task-field-label">环境变量</span>
                                    <v-btn variant="text" rounded="lg" size="x-small" prepend-icon="mdi-plus"
                                        :disabled="addEnvVarDisabled" @click="handleAddEnvVarClick">
                                        添加
                                    </v-btn>
                                </div>

                                <v-sheet color="transparent">
                                    <v-list v-if="form.env_var_refs.length" bg-color="transparent" density="compact"
                                        class="pa-0">
                                        <v-list-item v-for="(env, index) in form.env_var_refs" :key="index" rounded="lg"
                                            class="px-0 py-1">
                                            <v-select :model-value="env.key" :items="optionsForIndex(index)"
                                                item-title="key" item-value="key" placeholder="选择变量"
                                                variant="solo-filled" flat rounded="lg" hide-details density="compact"
                                                class="task-editor-field"
                                                @update:model-value="handleEnvSelection(index, $event)" />
                                            <template #append>
                                                <v-btn icon="mdi-close" variant="text" size="x-small"
                                                    aria-label="移除环境变量" @click="emit('remove-env-var', index)" />
                                            </template>
                                        </v-list-item>
                                    </v-list>
                                </v-sheet>
                            </div>
                        </div>
                    </aside>

                    <section class="task-editor-main">
                        <v-sheet color="transparent" class="task-editor-code">
                            <MonacoEditor v-model="form.payload"
                                :language="form.execution_mode === 'script' ? 'python' : 'markdown'"
                                :show-line-numbers="form.execution_mode === 'script'" />
                        </v-sheet>
                    </section>
                </div>
            </v-card-text>

            <v-divider />

            <v-card-actions class="px-4 py-2 flex-shrink-0">
                <v-spacer />
                <v-btn variant="text" rounded="lg" size="small" @click="emit('update:modelValue', false)">取消</v-btn>
                <v-btn color="primary" rounded="lg" size="small" :loading="saving"
                    :disabled="!form.name.trim() || !!cronError" @click="emit('save')">
                    {{ actionLabel }}
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script setup lang="ts">
    import MonacoEditor from '@/components/editor/MonacoEditor.vue'
    import { MODE_ICON, MODE_LABEL, validateCronExpression, type EnvVarRef, type Task } from '@/utils/tasks'

    interface EditorForm {
        name: string
        description: string
        execution_mode: Task['execution_mode']
        payload: string
        cron_expression: string
        env_var_refs: EnvVarRef[]
    }

    const props = defineProps<{
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
        'request-env-vars-setup': []
        save: []
    }>()

    const cronError = computed(() => validateCronExpression(props.form.cron_expression))

    const hasUnselectedEnvRef = computed(() =>
        props.form.env_var_refs.some((item) => !item.key.trim())
    )

    const canAddEnvVar = computed(() =>
        props.savedEnvVars.length > 0 && !hasUnselectedEnvRef.value && props.form.env_var_refs.length < props.savedEnvVars.length
    )

    const addEnvVarDisabled = computed(() =>
        hasUnselectedEnvRef.value || (props.savedEnvVars.length > 0 && props.form.env_var_refs.length >= props.savedEnvVars.length)
    )

    function optionsForIndex (index: number): EnvVarRef[] {
        const currentKey = props.form.env_var_refs[index]?.key
        const selectedByOthers = new Set(
            props.form.env_var_refs
                .filter((_, rowIndex) => rowIndex !== index)
                .map((item) => item.key)
                .filter(Boolean)
        )

        return props.savedEnvVars.filter((item) =>
            item.key === currentKey || !selectedByOthers.has(item.key)
        )
    }

    function handleAddEnvVarClick () {
        if (!props.savedEnvVars.length) {
            emit('request-env-vars-setup')
            return
        }
        if (!canAddEnvVar.value) return
        emit('add-env-var')
    }

    function handleEnvSelection (index: number, selectedKey: string | null) {
        const target = props.form.env_var_refs[index]
        if (!target) return

        target.key = selectedKey ?? ''
    }
</script>

<style scoped>
    .task-editor-card {
        height: min(680px, calc(100vh - 64px));
        max-height: min(680px, calc(100vh - 64px));
    }

    .task-editor-body {
        display: flex;
        flex: 1 1 auto;
        min-height: 0;
        overflow: hidden;
    }

    .task-editor-layout {
        display: grid;
        flex: 1 1 auto;
        grid-template-columns: 272px minmax(0, 1fr);
        width: 100%;
        min-height: 0;
        overflow: hidden;
    }

    .task-editor-sidebar {
        height: 100%;
        max-height: 100%;
        min-height: 0;
        overflow-y: auto;
    }

    .task-editor-sidebar-inner {
        display: grid;
        gap: 12px;
        padding: 12px;
    }

    .task-editor-panel {
        display: grid;
        gap: 7px;
    }

    .task-editor-section-title {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        color: rgba(var(--v-theme-on-surface), 0.72);
        font-size: 0.8125rem;
        font-weight: 700;
        line-height: 1.25rem;
    }

    .task-field-label {
        color: rgba(var(--v-theme-on-surface), 0.62);
        font-size: 0.75rem;
        font-weight: 500;
        line-height: 1rem;
    }

    .task-editor-field :deep(.v-field) {
        background: rgba(var(--v-theme-on-surface), 0.045) !important;
        box-shadow: none !important;
    }

    .task-editor-field :deep(.v-field__input) {
        min-height: 34px;
        padding-top: 5px;
        padding-bottom: 5px;
        font-size: 0.8125rem;
    }

    .task-editor-textarea :deep(.v-field__input) {
        min-height: 56px;
    }

    .task-editor-toggle {
        background: rgba(var(--v-theme-on-surface), 0.045);
    }

    .task-editor-toggle :deep(.v-btn) {
        min-width: 0;
        height: 30px;
        font-size: 0.75rem;
    }

    .task-preset-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
    }

    .task-preset-grid :deep(.v-btn) {
        height: 24px;
        padding-inline: 8px;
        font-size: 0.72rem;
    }

    .task-env-inline {
        display: grid;
        gap: 5px;
        padding-top: 2px;
    }

    .task-env-inline :deep(.v-list-item) {
        min-height: 34px;
    }

    .task-env-inline-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-height: 24px;
    }

    .task-env-inline-header :deep(.v-btn) {
        height: 24px;
        padding-inline: 6px;
        font-size: 0.75rem;
    }

    .task-empty-state {
        min-height: 22px;
        font-size: 0.75rem;
        line-height: 1.25rem;
    }

    .task-editor-main {
        display: flex;
        flex-direction: column;
        min-width: 0;
        height: 100%;
        min-height: 0;
    }

    .task-editor-code {
        flex: 1 1 0;
        height: auto;
        min-height: 0;
    }

    @media (max-width: 760px) {
        .task-editor-card {
            max-height: calc(100vh - 32px);
        }

        .task-editor-body {
            overflow-y: auto;
        }

        .task-editor-layout {
            grid-template-columns: 1fr;
            height: auto;
        }

        .task-editor-sidebar {
            border-right: 0 !important;
            border-bottom: thin solid rgba(var(--v-border-color), var(--v-border-opacity));
        }

        .task-editor-code {
            height: 320px;
        }
    }
</style>
