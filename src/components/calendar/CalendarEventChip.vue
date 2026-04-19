<template>
    <v-btn block height="20" min-width="0" rounded="sm" variant="text" class="pa-0 ma-0 overflow-hidden justify-start align-stretch text-none" type="button" :title="event.title" :style="chipStyle" @mouseenter="isHovered = true" @mouseleave="isHovered = false" @click.stop="$emit('click', event)" @contextmenu.prevent.stop="$emit('contextmenu', { event, mouseEvent: $event })">
        <span :style="sourceStyle"></span>
        <span class="flex-grow-1" :style="contentStyle">
            <span class="flex-shrink-0" :style="timeStyle">{{ timeLabel }}</span>
            <span :style="titleStyle">{{ event.title }}</span>
        </span>
    </v-btn>
</template>

<script setup lang="ts">
    import type { CalEvent } from '@/types/calendar'
    import { getEventChipTimeLabel } from '@/utils/calendar'

    const props = withDefaults(defineProps<{ event: CalEvent; dimmed?: boolean; sourceColorMap?: Record<string, string> }>(), {
        dimmed: false,
    })
    defineEmits<{
        click: [event: CalEvent]
        contextmenu: [payload: { event: CalEvent; mouseEvent: MouseEvent }]
    }>()

    const isHovered = ref(false)
    const timeLabel = computed(() => getEventChipTimeLabel(props.event))
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
        width: '4px',
        height: '100%',
        flexShrink: 0,
        backgroundColor: sourceColor.value,
    }))
    const contentStyle = computed(() => ({
        display: 'grid',
        gridTemplateColumns: 'max-content minmax(0, 1fr)',
        alignItems: 'center',
        height: '100%',
        columnGap: '3px',
        minWidth: '0',
        overflow: 'hidden',
        padding: '0 2px',
        color: 'rgba(var(--v-theme-on-surface), 0.95)',
    }))
    const titleStyle = {
        display: 'block',
        minWidth: '0',
        overflow: 'hidden',
        whiteSpace: 'nowrap',
        textOverflow: 'ellipsis',
        fontSize: '11px',
        fontWeight: 500,
    }
    const timeStyle = {
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        fontSize: '11px',
        opacity: '0.8',
    }
</script>
