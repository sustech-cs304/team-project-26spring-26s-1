<template>
    <v-tooltip :text="title" :location="location">
        <template v-slot:activator="{ props }">
            <v-list-item v-bind="{ ...props, ...$attrs }" link :prepend-icon="icon">
                <!-- <v-icon :icon="icon"></v-icon> -->
            </v-list-item>
        </template>
    </v-tooltip>
</template>

<script setup>
    defineProps({
        title: String,
        icon: String,
        location: { type: String, default: 'left' }
    })
</script>
