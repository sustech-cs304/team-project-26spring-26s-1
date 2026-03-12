<template>
    <v-chip :color="eventTypeColor(event.type)" variant="tonal" size="x-small" density="compact" label
        class="chip-chip w-100" :title="event.title"
        style="font-size:10px;height:16px;border-radius:3px;cursor:pointer;" @click.stop="$emit('click', event)">
        <span class="chip-dot mr-1" />
        <span class="chip-text">{{ event.title }}</span>
    </v-chip>
</template>

<script setup lang="ts">
    import type { CalEvent } from '@/utils/calendar'
    defineProps<{ event: CalEvent }>()
    defineEmits<{ click: [event: CalEvent] }>()

    function eventTypeColor (type: CalEvent['type']) {
        const map: Record<string, string> = {
            exam: 'error',
            class: 'primary',
            personal: 'info',
            deadline: 'warning',
            meeting: 'secondary',
        }
        return map[type] ?? 'primary'
    }
</script>

<style scoped>
    .chip-dot {
        width: 5px;
        height: 5px;
        border-radius: 50%;
        flex-shrink: 0;
        background: currentColor;
        opacity: 0.7;
        display: inline-block;
    }

    .chip-text {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
</style>
