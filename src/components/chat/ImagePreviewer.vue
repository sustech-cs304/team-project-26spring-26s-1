<template>
    <Teleport to="body">
        <Transition name="image-preview-fade">
            <div v-if="model" class="image-preview-backdrop" @click.self="close" @wheel.prevent="handleWheel">
                <div class="image-preview-controls" @click.stop>
                    <v-tooltip text="Zoom out" location="bottom">
                        <template #activator="{ props: tooltipProps }">
                            <v-btn v-bind="tooltipProps" icon="mdi-minus" size="small" variant="flat"
                                density="comfortable" @click="zoomBy(0.85)" />
                        </template>
                    </v-tooltip>
                    <v-tooltip text="Reset" location="bottom">
                        <template #activator="{ props: tooltipProps }">
                            <v-btn v-bind="tooltipProps" icon="mdi-fit-to-page-outline" size="small" variant="flat"
                                density="comfortable" @click="resetView" />
                        </template>
                    </v-tooltip>
                    <v-tooltip text="Zoom in" location="bottom">
                        <template #activator="{ props: tooltipProps }">
                            <v-btn v-bind="tooltipProps" icon="mdi-plus" size="small" variant="flat"
                                density="comfortable" @click="zoomBy(1.15)" />
                        </template>
                    </v-tooltip>
                    <v-tooltip text="Close" location="bottom">
                        <template #activator="{ props: tooltipProps }">
                            <v-btn v-bind="tooltipProps" icon="mdi-close" size="small" variant="flat"
                                density="comfortable" @click="close" />
                        </template>
                    </v-tooltip>
                </div>

                <img class="image-preview-image" :class="{ 'image-preview-image--dragging': dragging }" :src="src"
                    :alt="alt" draggable="false" :style="imageStyle" @click.stop @pointerdown="startDrag" />
            </div>
        </Transition>
    </Teleport>
</template>

<script setup lang="ts">
    const model = defineModel<boolean>({ default: false })

    const props = defineProps<{
        src: string
        alt?: string
    }>()

    const scale = ref(1)
    const offset = reactive({ x: 0, y: 0 })
    const dragging = ref(false)
    const dragStart = reactive({ x: 0, y: 0, offsetX: 0, offsetY: 0 })

    const imageStyle = computed(() => ({
        transform: `translate3d(${offset.x}px, ${offset.y}px, 0) scale(${scale.value})`,
    }))

    function clampScale (value: number) {
        return Math.min(6, Math.max(0.25, value))
    }

    function resetView () {
        scale.value = 1
        offset.x = 0
        offset.y = 0
    }

    function close () {
        model.value = false
        resetView()
    }

    function zoomBy (factor: number) {
        scale.value = clampScale(scale.value * factor)
    }

    function handleWheel (event: WheelEvent) {
        zoomBy(event.deltaY > 0 ? 0.9 : 1.1)
    }

    function startDrag (event: PointerEvent) {
        event.preventDefault()
        dragging.value = true
        dragStart.x = event.clientX
        dragStart.y = event.clientY
        dragStart.offsetX = offset.x
        dragStart.offsetY = offset.y
        window.addEventListener('pointermove', handleDrag)
        window.addEventListener('pointerup', stopDrag, { once: true })
        window.addEventListener('pointercancel', stopDrag, { once: true })
    }

    function handleDrag (event: PointerEvent) {
        if (!dragging.value) return
        offset.x = dragStart.offsetX + event.clientX - dragStart.x
        offset.y = dragStart.offsetY + event.clientY - dragStart.y
    }

    function stopDrag () {
        dragging.value = false
        window.removeEventListener('pointermove', handleDrag)
    }

    function handleKeydown (event: KeyboardEvent) {
        if (event.key === 'Escape' && model.value) close()
    }

    watch(
        () => [model.value, props.src],
        () => resetView()
    )

    onMounted(() => {
        window.addEventListener('keydown', handleKeydown)
    })

    onBeforeUnmount(() => {
        window.removeEventListener('keydown', handleKeydown)
        window.removeEventListener('pointermove', handleDrag)
    })
</script>

<style scoped>
    .image-preview-backdrop {
        position: fixed;
        inset: 0;
        z-index: 3000;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        background: rgba(0, 0, 0, 0.78);
        cursor: zoom-out;
    }

    .image-preview-controls {
        position: fixed;
        top: 18px;
        right: 18px;
        z-index: 1;
        display: flex;
        gap: 8px;
    }

    .image-preview-controls :deep(.v-btn) {
        color: rgb(var(--v-theme-on-surface));
        background: rgba(var(--v-theme-surface), 0.9) !important;
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.24);
    }

    .image-preview-image {
        max-width: 92vw;
        max-height: 88vh;
        object-fit: contain;
        border-radius: 8px;
        cursor: grab;
        user-select: none;
        touch-action: none;
        transition: transform 0.08s ease-out;
        box-shadow: 0 20px 70px rgba(0, 0, 0, 0.45);
    }

    .image-preview-image--dragging {
        cursor: grabbing;
        transition: none;
    }

    .image-preview-fade-enter-active,
    .image-preview-fade-leave-active {
        transition: opacity 0.16s ease;
    }

    .image-preview-fade-enter-from,
    .image-preview-fade-leave-to {
        opacity: 0;
    }
</style>
