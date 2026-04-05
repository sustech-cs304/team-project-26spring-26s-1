<template>
    <v-btn block height="20" min-width="0" rounded="sm" variant="text" class="pa-0 ma-0 overflow-hidden justify-start align-stretch text-none" type="button" :title="event.title" :style="chipStyle" @mouseenter="isHovered = true" @mouseleave="isHovered = false" @click.stop="$emit('click', event)" @contextmenu.prevent.stop="$emit('contextmenu', { event, mouseEvent: $event })">
        <span :style="sourceStyle"></span>
        <span class="d-flex align-center flex-grow-1" :style="contentStyle">
            <span class="text-truncate flex-grow-1" :style="titleStyle">{{ event.title }}</span>
            <span class="flex-shrink-0" :style="timeStyle">{{ event.time }}</span>
        </span>
    </v-btn>
</template>

<script setup lang="ts">
    import type { CalEvent } from '@/types/calendar'

    const props = withDefaults(defineProps<{ event: CalEvent; dimmed?: boolean; sourceColorMap?: Record<string, string> }>(), {
        dimmed: false,
    })
    defineEmits<{
        click: [event: CalEvent]
        contextmenu: [payload: { event: CalEvent; mouseEvent: MouseEvent }]
    }>()

    const isHovered = ref(false)
    const sourceColor = computed(() => props.sourceColorMap?.[props.event.source] ?? '#2563eb')
    const fillColor = computed(() => props.event.color || '#3b82f6')
    const categoryColor = computed(() => `color-mix(in srgb, ${fillColor.value} 28%, transparent)`)
    const chipStyle = computed(() => ({
        minHeight: '20px',
        maxHeight: '20px',
        '--v-btn-height': '20px',
        backgroundColor: categoryColor.value,
        opacity: props.dimmed ? '0.35' : undefined,
        filter: props.dimmed ? 'grayscale(0.85)' : isHovered.value ? 'brightness(1.06)' : undefined,
    }))
    const sourceStyle = computed(() => ({
        width: '11px',
        height: '100%',
        flexShrink: 0,
        backgroundColor: sourceColor.value,
    }))
    const contentStyle = computed(() => ({
        height: '100%',
        gap: '5px',
        minWidth: '0',
        padding: '0 6px',
        color: 'rgba(var(--v-theme-on-surface), 0.95)',
    }))
    const titleStyle = {
        minWidth: '0',
        fontSize: '11px',
        fontWeight: 500,
    }
    const timeStyle = {
        whiteSpace: 'nowrap',
        fontSize: '9px',
        opacity: '0.72',
    }
</script>
