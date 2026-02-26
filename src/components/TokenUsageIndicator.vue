<template>
    <v-tooltip :text="tooltipText" location="left">
        <template #activator="{ props }">
            <div class="token-indicator justify-center " v-bind="props">
                <v-icon size="17" color="success">mdi-flash</v-icon>
                <v-progress-linear :model-value="percent" color="success" height="8" class="token-bar" rounded />
                <v-card-text :opacity="0.6" class="pa-0">
                    {{ percentText }}
                </v-card-text>
            </div>
        </template>
    </v-tooltip>
</template>

<script setup lang="ts">
    const props = defineProps<{
        usedTokens: number
        totalTokens: number
    }>()

    const percent = computed(() => {
        if (props.totalTokens <= 0) return 0
        const value = (props.usedTokens / props.totalTokens) * 100
        return Math.min(100, Math.max(0, Math.round(value)))
    })

    const percentText = computed(() => {
        if (percent.value === 100) return '100%'
        return `${String(percent.value).padStart(2, '0')}%`
    })

    const tooltipText = computed(() => {
        return `API: ${props.usedTokens} / ${props.totalTokens} tokens`
    })
</script>

<style scoped>
    .token-indicator {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 20px;
    }

    .token-bar {
        width: 39px;
        transform: translateX(-1px) translateY(-1px) rotate(-90deg);
        transform-origin: center;
    }
</style>
