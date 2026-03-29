<template>
    <button class="event-chip" type="button" :class="{ dimmed }" :title="event.title" @click.stop="$emit('click', event)">
        <span class="source-block" :style="{ backgroundColor: sourceColor }"></span>
        <span class="color-content" :style="{ backgroundColor: categoryColor }">
            <span class="title">{{ event.title }}</span>
            <span v-if="event.time" class="time">{{ event.time }}</span>
        </span>
    </button>
</template>

<script setup lang="ts">
    import type { CalEvent } from '@/utils/calendar'
    import { eventSourceRawColor } from '@/utils/calendar'

    const props = withDefaults(defineProps<{ event: CalEvent; dimmed?: boolean }>(), {
        dimmed: false,
    })
    defineEmits<{ click: [event: CalEvent] }>()

    const sourceColor = computed(() => eventSourceRawColor(props.event.source))
    const categoryColor = computed(() => `color-mix(in srgb, ${props.event.color || sourceColor.value} 28%, transparent)`)
</script>

<style scoped>
    .event-chip {
        display: flex;
        align-items: stretch;
        width: 100%;
        height: 20px;
        border: none;
        border-radius: 4px;
        overflow: hidden;
        padding: 0;
        margin: 0;
        background: transparent;
        cursor: pointer;
        text-align: left;
    }

    .source-block {
        width: 11px;
        flex-shrink: 0;
    }

    .color-content {
        display: flex;
        align-items: center;
        gap: 5px;
        flex: 1;
        min-width: 0;
        padding: 0 6px;
        color: rgba(var(--v-theme-on-surface), 0.95);
    }

    .title {
        font-size: 11px;
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        flex: 1;
        min-width: 0;
    }

    .time {
        font-size: 9px;
        opacity: 0.72;
        white-space: nowrap;
        flex-shrink: 0;
    }

    .event-chip:hover .color-content {
        filter: brightness(1.06);
    }

    .event-chip.dimmed {
        opacity: 0.35;
        filter: grayscale(0.85);
    }

    .event-chip.dimmed:hover .color-content {
        filter: none;
    }
</style>
