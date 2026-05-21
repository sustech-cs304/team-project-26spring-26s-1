<template>
    <v-menu open-on-hover :close-on-content-click="false" location="right center" offset="10"
        transition="scale-transition">
        <template #activator="{ props }">
            <v-btn v-bind="props" variant="text" class="mcp-indicator" :ripple="false">
                <v-icon size="16" :color="summaryColor">{{ summaryIcon }}</v-icon>
                <span class="mcp-indicator__count" :class="`text-${summaryColor}`">
                    {{ statusCountLabel }}
                </span>
            </v-btn>
        </template>

        <v-sheet rounded="lg" border color="surface" class="mcp-popover pa-3">
            <div class="d-flex align-center ga-2 mb-2">
                <v-icon size="18" :color="summaryColor">{{ summaryIcon }}</v-icon>
                <div class="text-body-2 font-weight-bold">MCP</div>
                <v-chip size="x-small" variant="tonal" :color="summaryColor">
                    {{ summaryLabel }}
                </v-chip>
            </div>

            <v-divider class="mb-2" />

            <v-list bg-color="transparent" density="compact" class="pa-0 mcp-status-list">
                <template v-if="enabledStatuses.length">
                    <v-list-item v-for="entry in enabledStatuses" :key="entry.name" rounded="lg" class="px-2 mb-1">
                        <template #prepend>
                            <v-icon size="16" :color="entry.status === 'running' ? 'success' : 'error'">
                                {{ entry.status === 'running' ? 'mdi-check-circle-outline' : 'mdi-alert-circle-outline' }}
                            </v-icon>
                        </template>

                        <v-list-item-title class="text-body-2">
                            {{ entry.name }}
                        </v-list-item-title>
                        <v-list-item-subtitle class="text-caption">
                            {{ entry.status }}
                        </v-list-item-subtitle>

                        <template #append>
                            <v-chip
                                size="x-small"
                                variant="tonal"
                                :color="entry.status === 'running' ? 'success' : 'error'"
                            >
                                {{ entry.status === 'running' ? 'Alive' : 'Down' }}
                            </v-chip>
                        </template>
                    </v-list-item>
                </template>

                <v-list-item v-else class="px-2">
                    <v-list-item-title class="text-body-2">
                        No enabled MCP servers
                    </v-list-item-title>
                </v-list-item>
            </v-list>
        </v-sheet>
    </v-menu>
</template>

<script setup lang="ts">
    import { computed, onMounted } from 'vue'
    import { useMcpStatus } from '@/composables/useMcpStatus'

    const {
        enabledStatuses,
        aliveStatuses,
        summaryIcon,
        summaryLabel,
        summaryColor,
        startMcpStatusPolling,
    } = useMcpStatus()

    const statusCountLabel = computed(() => `${aliveStatuses.value.length}/${enabledStatuses.value.length}`)

    onMounted(() => {
        startMcpStatusPolling()
    })
</script>

<style scoped>
    .mcp-indicator {
        width: 100%;
        min-width: 0;
        min-height: 48px;
        padding: 6px 0;
        text-transform: none;
    }

    .mcp-indicator :deep(.v-btn__content) {
        width: 100%;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 1px;
    }

    .mcp-indicator__count {
        font-size: 0.62rem;
        font-weight: 700;
        line-height: 1;
        letter-spacing: 0;
        white-space: nowrap;
    }

    .mcp-popover {
        width: 264px;
        max-width: calc(100vw - 72px);
    }

    .mcp-status-list :deep(.v-list-item-title) {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
</style>
