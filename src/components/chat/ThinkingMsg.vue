<template>
    <div class="text-body-medium opacity-80 pa-1">
        <span class="d-flex align-center" style="gap: 4px;">
            <v-icon size="16">mdi-lightbulb-outline</v-icon>
            <span v-if="isActive" class="typing-shimmer">Thinking...</span>
            <span v-else>Thinking</span>
        </span>
    </div>
    <div class="steps-timeline font-weight-light text-body-medium opacity-80">
        {{ content }}
    </div>
</template>

<script setup lang="ts">

    const props = defineProps<{
        content: string
        isActive?: boolean
    }>()

</script>

<style scoped>
    .steps-timeline {
        border-left: 2px solid rgba(var(--v-theme-on-surface), 0.12);
        margin-left: 11px;
        padding-left: 10px;
    }
</style>
