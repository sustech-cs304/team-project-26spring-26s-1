<template>
    <v-menu open-on-hover :close-on-content-click="false" location="right center" offset="10"
        transition="scale-transition">
        <template #activator="{ props }">
            <v-btn v-bind="props" variant="text" width="100%" height="48" min-width="0" class="px-0 text-none"
                :ripple="false">
                <span class="d-flex flex-column align-center justify-center ga-0 w-100">
                    <v-icon size="16">{{ summaryIcon }}</v-icon>
                    <span class="text-caption font-weight-bold text-no-wrap">
                        {{ statusCountLabel }}
                    </span>
                </span>
            </v-btn>
        </template>

        <v-sheet rounded="lg" border color="surface" width="264" max-width="calc(100vw - 72px)" class="pa-3">
            <div class="d-flex align-center ga-2 mb-2">
                <v-icon size="18">{{ summaryIcon }}</v-icon>
                <div class="text-body-2 font-weight-bold">MCP</div>
                <v-chip size="x-small" variant="tonal">
                    {{ summaryLabel }}
                </v-chip>
            </div>

            <v-divider class="mb-2" />

            <v-list bg-color="transparent" density="compact" class="pa-0">
                <template v-if="enabledStatuses.length">
                    <v-list-item v-for="entry in enabledStatuses" :key="entry.name" rounded="lg" class="px-2 mb-1">
                        <template #prepend>
                            <v-icon size="16">
                                {{ entry.status === 'running' ? 'mdi-check-circle-outline' : 'mdi-alert-circle-outline' }}
                            </v-icon>
                        </template>

                        <v-list-item-title class="text-body-2 text-truncate">
                            {{ entry.name }}
                        </v-list-item-title>
                        <v-list-item-subtitle class="text-caption">
                            {{ entry.status }}
                        </v-list-item-subtitle>

                        <template #append>
                            <v-chip size="x-small" variant="tonal">
                                {{ entry.status === 'running' ? 'Alive' : 'Down' }}
                            </v-chip>
                        </template>
                    </v-list-item>
                </template>

                <v-list-item v-else class="px-2">
                    <v-list-item-title class="text-body-2 text-truncate">
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
        startMcpStatusPolling,
    } = useMcpStatus()

    const statusCountLabel = computed(() => `${aliveStatuses.value.length}/${enabledStatuses.value.length}`)

    onMounted(() => {
        startMcpStatusPolling()
    })
</script>
