<template>
    <button class="thinking-toggle text-body-medium opacity-80 pa-1" type="button" @click="expanded = !expanded">
        <span class="d-flex align-center" style="gap: 4px;">
            <v-icon size="16">{{ expanded ? 'mdi-chevron-down' : 'mdi-chevron-right' }}</v-icon>
            <v-icon size="16">mdi-lightbulb-outline</v-icon>
            <span v-if="isActive" class="typing-shimmer">Thinking...</span>
            <span v-else>Thinking</span>
        </span>
    </button>
    <div v-if="expanded" class="steps-timeline font-weight-light text-body-medium opacity-80">
        {{ content }}
    </div>
</template>

<script setup lang="ts">
    const props = defineProps<{
        content: string
        isActive?: boolean
        autoCollapse?: boolean
    }>()

    const expanded = ref(!props.autoCollapse)

    watch(() => props.autoCollapse, (next, prev) => {
        if (next && !prev) {
            expanded.value = false
        }
    })

</script>

<style scoped>
    .thinking-toggle {
        display: flex;
        align-items: center;
        background: transparent;
        border: 0;
        width: 100%;
        text-align: left;
        cursor: pointer;
    }

    .steps-timeline {
        border-left: 2px solid rgba(var(--v-theme-on-surface), 0.12);
        margin-left: 11px;
        padding-left: 10px;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
    }
</style>
