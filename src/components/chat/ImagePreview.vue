<template>
    <v-row density="compact" class="ga-2 flex-wrap" style="max-width: calc(9 * (72px + 8px))">
        <v-col v-for="(img, i) in images" :key="i" cols="auto" class="position-relative">
            <v-img :src="img" width="72" height="72" cover rounded="lg" />
            <v-btn icon="mdi-close" size="x-small" density="compact" variant="flat" color="surface" rounded="circle"
                class="position-absolute" style="top: -3px; right: -3px; width: 18px; height: 18px; min-width: 0;"
                @click="remove(i)" />
        </v-col>
    </v-row>
</template>

<script setup lang="ts">
    const images = defineModel<string[]>({ default: () => [] })

    const remove = (i: number) => {
        images.value = images.value.filter((_, idx) => idx !== i)
    }
</script>
