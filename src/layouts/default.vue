<template>
    <v-layout class="h-100 overflow-hidden">
        <v-navigation-drawer v-if="!isBackendBlocking" permanent rail rail-width="42">
            <v-divider />
            <v-list nav class="px-0 flex-grow-1 py-0">
                <nav-icon-item v-if="!onboardingCompleted" title="Home" icon="mdi-home" to="/"
                    :disabled="isBackendBlocking" />
                <nav-icon-item title="Chat" icon="mdi-message-outline"
                    v-bind="route.path.startsWith('/c/') ? {} : { to: '/c/' }" :disabled="isBackendBlocking" />
                <nav-icon-item title="Tasks" icon="mdi-format-list-checkbox" to="/tasks"
                    :disabled="isBackendBlocking" />
                <nav-icon-item title="Calendar" icon="mdi-calendar" to="/calendar" :disabled="isBackendBlocking" />
                <nav-icon-item title="Store" icon="mdi-connection" to="/store" :disabled="isBackendBlocking" />
            </v-list>
            <template #append>
                <div class="d-flex flex-column align-center ga-3 py-3">
                    <McpStatusIndicator />
                </div>
                <v-list nav class="px-0 py-0">
                    <nav-icon-item title="Settings" icon="mdi-cog" to="/settings" :disabled="isBackendBlocking" />
                </v-list>
            </template>
        </v-navigation-drawer>

        <v-main class="h-100 overflow-hidden position-relative">
            <router-view v-show="!isBackendBlocking" />
            <BackendHealthOverlay v-show="isBackendBlocking" />
        </v-main>
    </v-layout>
</template>
<script setup lang="ts">
    import BackendHealthOverlay from '@/components/BackendHealthOverlay.vue'
    import McpStatusIndicator from '@/components/McpStatusIndicator.vue'
    import NavIconItem from '@/components/NavIconItem.vue'
    import { useBackendHealth } from '@/composables/useBackendHealth'
    import { useOnboardingConfig } from '@/composables/useOnboardingConfig'

    const route = useRoute()
    const { isBlocking: isBackendBlocking } = useBackendHealth()
    const { onboardingCompleted } = useOnboardingConfig()
</script>
