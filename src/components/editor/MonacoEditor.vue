<template>
    <div class="h-100 w-100 monaco-shell">
        <vue-monaco-editor
            v-model:value="value"
            :language="language"
            :theme="editorTheme"
            :options="editorOptions"
            style="width:100%;height:100%;"
        />
    </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTheme } from 'vuetify'

interface Props {
    modelValue: string
    language?: string
    readOnly?: boolean
    showLineNumbers?: boolean
    wordWrap?: 'off' | 'on' | 'wordWrapColumn' | 'bounded'
}

const props = withDefaults(defineProps<Props>(), {
    language: 'python',
    readOnly: false,
    showLineNumbers: true,
    wordWrap: 'on'
})

const emit = defineEmits<{
    (e: 'update:modelValue', value: string): void
}>()

const theme = useTheme()
const editorTheme = computed(() => theme.current.value.dark ? 'vs-dark' : 'vs')

const editorOptions = computed(() => ({
    readOnly: props.readOnly,
    minimap: { enabled: false },
    wordWrap: props.wordWrap,
    scrollBeyondLastLine: false,
    automaticLayout: true,
    fontSize: 14,
    lineNumbers: props.showLineNumbers ? 'on' : 'off',
    renderLineHighlight: props.readOnly ? 'none' : 'line',
    overviewRulerLanes: 0,
    scrollbar: {
        verticalScrollbarSize: 6,
        horizontalScrollbarSize: 6,
    },
    padding: { top: 12, bottom: 12 },
    folding: true,
    lineDecorationsWidth: 10,
    lineNumbersMinChars: 3,
    renderWhitespace: 'none',
    tabSize: 4,
    insertSpaces: true,
    detectIndentation: true,
    autoIndent: 'full',
    formatOnType: true,
    formatOnPaste: true,
    suggestOnTriggerCharacters: true,
    acceptSuggestionOnEnter: 'on',
    snippetSuggestions: 'inline',
}))

const value = computed({
    get: () => props.modelValue,
    set: (next: string) => emit('update:modelValue', next),
})
</script>

<style scoped>
    .monaco-shell {
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        border-radius: 8px;
        overflow: hidden;
    }
</style>
