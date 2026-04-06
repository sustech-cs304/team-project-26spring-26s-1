<template>
    <div v-for="log in logs" :key="log.id" class="log-line">
        <span v-if="log.log_type === 'script_start'" class="log-start">── Script started ──</span>
        <span v-if="log.log_type === 'script_start'" class="log-meta">Python {{ log.metadata.python_version }} · {{ log.metadata.platform }}<span v-if="log.metadata.injected_env_keys?.length"> · env: {{ log.metadata.injected_env_keys.join(',') }}</span></span>
        <span v-else-if="log.log_type === 'script_stdout'" class="terminal-stdout">{{ log.content }}</span>
        <span v-else-if="log.log_type === 'script_stderr'" class="terminal-stderr">{{ log.content }}</span>
        <template v-else-if="log.log_type === 'script_end'">
            <span :class="log.metadata.exit_code === 0 ? 'terminal-ok' : 'terminal-fail'">── Exited with code {{ log.metadata.exit_code }} ──</span>
            <span class="terminal-meta">{{ log.duration_ms }}ms</span>
        </template>
        <span v-else-if="log.log_type === 'tool_call'" class="terminal-tool">[tool] {{ log.tool_name }}</span>
    </div>
</template>

<script setup lang="ts">
import type { LogEntry } from '@/utils/tasks'

defineProps<{
    logs: LogEntry[]
}>()
</script>
