<template>
    <v-sheet
        v-if="isBlocking"
        color="background"
        class="position-absolute top-0 right-0 bottom-0 left-0 d-flex align-center justify-center"
    >
        <v-sheet
            color="background"
            rounded="xl"
            max-width="560"
            width="100%"
            class="pa-8 d-flex flex-column align-center text-center"
        >
            <v-progress-circular
                v-if="!hasTimedOut"
                indeterminate
                size="52"
                width="4"
                class="mb-6"
            />
            <v-icon
                v-else
                icon="mdi-lan-disconnect"
                size="52"
                class="mb-6 text-medium-emphasis"
            />

            <div class="text-h5 font-weight-bold mb-3">
                {{ title }}
            </div>
            <div class="text-body-1 text-medium-emphasis mb-6">
                {{ message }}
            </div>

            <v-btn
                v-if="hasTimedOut"
                rounded="lg"
                variant="tonal"
                prepend-icon="mdi-refresh"
                :loading="isCheckingNow"
                @click="retryBackendHealthCheck"
            >
                重新检测
            </v-btn>
        </v-sheet>
    </v-sheet>
</template>

<script setup lang="ts">
    import { onMounted } from 'vue'
    import { useBackendHealth } from '@/composables/useBackendHealth'

    const {
        title,
        message,
        isBlocking,
        isCheckingNow,
        hasTimedOut,
        startBackendHealthPolling,
        retryBackendHealthCheck,
    } = useBackendHealth()

    onMounted(() => {
        startBackendHealthPolling()
    })
</script>
