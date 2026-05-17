<template>
    <v-btn ref="chipEl" block height="20" min-width="0" rounded="0" variant="text" class="calendar-event-chip pa-0 ma-0 overflow-hidden justify-start align-stretch text-none"
        type="button" :title="event.title" :style="chipStyle" :draggable="draggable ? 'true' : 'false'"
        @click.stop="$emit('click', event)"
        @contextmenu.prevent.stop="$emit('contextmenu', { event, mouseEvent: $event })"
        @dragstart.stop="onDragStart" @dragend.stop="$emit('dragend', event)">
        <span :style="sourceStyle"></span>
        <span class="flex-grow-1" :style="contentStyle">
            <span class="flex-shrink-0" :style="timeStyle">{{ timeLabel }}</span>
            <span :style="titleStyle">{{ event.title }}</span>
        </span>
    </v-btn>
</template>

<script setup lang="ts">
    import type { CSSProperties } from 'vue'
    import type { CalEvent } from '@/types/calendar'
    import { getEventChipTimeLabel } from '@/utils/calendar'
    import { normalizeCalendarColor, normalizeOptionalCalendarColor } from '@/utils/calendarColors'

    const props = withDefaults(defineProps<{ event: CalEvent; draggable?: boolean; selected?: boolean; sourceColorMap?: Record<string, string> }>(), {
        draggable: false,
        selected: false,
    })
    const emit = defineEmits<{
        click: [event: CalEvent]
        contextmenu: [payload: { event: CalEvent; mouseEvent: MouseEvent }]
        dragstart: [payload: { event: CalEvent; dragEvent: DragEvent }]
        dragend: [event: CalEvent]
    }>()

    const chipEl = ref<HTMLElement | { $el?: HTMLElement } | null>(null)
    const timeLabel = computed(() => getEventChipTimeLabel(props.event))
    const sourceColor = computed(() => normalizeCalendarColor(props.sourceColorMap?.[props.event.source], '#4ca8df'))
    const fillColor = computed(() => normalizeOptionalCalendarColor(props.event.color) ?? sourceColor.value)
    const chipStyle = computed<CSSProperties>(() => ({
        minHeight: '20px',
        maxHeight: '20px',
        '--v-btn-height': '20px',
        borderRadius: '7px',
        backgroundColor: 'transparent',
        cursor: props.draggable ? 'grab' : 'pointer',
    }))
    const sourceStyle = computed<CSSProperties>(() => ({
        width: '5px',
        height: '100%',
        flexShrink: 0,
        backgroundColor: sourceColor.value,
    }))
    const contentStyle = computed<CSSProperties>(() => ({
        display: 'flex',
        alignItems: 'center',
        height: '100%',
        columnGap: '3px',
        minWidth: '0',
        overflow: 'hidden',
        padding: '0 7px 0 0',
        backgroundColor: props.selected ? fillColor.value : 'transparent',
        color: props.selected ? '#fff' : fillColor.value,
        textAlign: 'left',
    }))
    const titleStyle = computed<CSSProperties>(() => ({
        display: 'block',
        flex: '1 1 auto',
        minWidth: '0',
        overflow: 'hidden',
        whiteSpace: 'nowrap',
        textOverflow: 'ellipsis',
        fontSize: '11px',
        lineHeight: '20px',
        fontWeight: props.selected ? 600 : 500,
        textAlign: 'left',
    }))
    const timeStyle = computed<CSSProperties>(() => ({
        whiteSpace: 'nowrap',
        flex: '0 0 auto',
        overflow: 'hidden',
        fontSize: '11px',
        lineHeight: '20px',
        fontWeight: props.selected ? 600 : 500,
        textAlign: 'left',
    }))

    const setDragImage = (dragEvent: DragEvent) => {
        if (!dragEvent.dataTransfer || typeof document === 'undefined') return

        const rawChipEl = chipEl.value
        const renderedChipEl = rawChipEl instanceof HTMLElement ? rawChipEl : rawChipEl?.$el
        const width = Math.max(96, Math.min(180, renderedChipEl?.getBoundingClientRect().width ?? 128))
        const preview = document.createElement('div')
        const strip = document.createElement('span')
        const content = document.createElement('span')
        const time = document.createElement('span')
        const title = document.createElement('span')

        Object.assign(preview.style, {
            position: 'fixed',
            top: '-1000px',
            left: '-1000px',
            zIndex: '-1',
            display: 'flex',
            width: `${width}px`,
            height: '20px',
            overflow: 'hidden',
            borderRadius: '7px',
            pointerEvents: 'none',
            background: 'transparent',
        })
        Object.assign(strip.style, {
            width: '5px',
            flexShrink: '0',
            background: sourceColor.value,
        })
        Object.assign(content.style, {
            display: 'flex',
            alignItems: 'center',
            columnGap: '3px',
            flex: '1 1 auto',
            minWidth: '0',
            padding: '0 7px 0 0',
            color: props.selected ? '#fff' : fillColor.value,
            background: props.selected ? fillColor.value : 'transparent',
            fontFamily: 'Roboto, sans-serif',
            fontSize: '11px',
            lineHeight: '20px',
            fontWeight: props.selected ? '600' : '500',
            textAlign: 'left',
        })
        Object.assign(time.style, {
            overflow: 'hidden',
            whiteSpace: 'nowrap',
        })
        Object.assign(title.style, {
            overflow: 'hidden',
            whiteSpace: 'nowrap',
            textOverflow: 'ellipsis',
        })

        time.textContent = timeLabel.value
        title.textContent = props.event.title
        content.append(time, title)
        preview.append(strip, content)
        document.body.append(preview)

        const offsetX = Math.max(8, Math.min(width - 8, dragEvent.offsetX || 12))
        dragEvent.dataTransfer.setDragImage(preview, offsetX, Math.min(10, dragEvent.offsetY || 10))
        window.requestAnimationFrame(() => preview.remove())
    }

    const onDragStart = (dragEvent: DragEvent) => {
        if (!props.draggable) {
            dragEvent.preventDefault()
            return
        }

        dragEvent.dataTransfer?.setData('text/plain', `${props.event.id}`)
        if (dragEvent.dataTransfer) {
            dragEvent.dataTransfer.effectAllowed = 'move'
            setDragImage(dragEvent)
        }
        emit('dragstart', { event: props.event, dragEvent })
    }
</script>

<style scoped>
    .calendar-event-chip :deep(.v-btn__overlay),
    .calendar-event-chip :deep(.v-btn__underlay) {
        display: none !important;
    }

    .calendar-event-chip :deep(.v-btn__content) {
        width: 100%;
        height: 100%;
        align-items: stretch;
        justify-content: flex-start;
        text-align: left;
    }
</style>
