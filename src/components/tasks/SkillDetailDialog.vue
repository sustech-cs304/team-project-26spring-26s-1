<template>
    <v-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" max-width="560"
        scrollable>
        <v-card v-if="skill" rounded="lg">

            <!-- 头图区域 -->
            <div class="skill-hero pa-5 d-flex align-start ga-4">
                <v-avatar :color="skill.color" rounded="lg" size="52">
                    <v-icon :size="26" color="white">{{ skill.icon }}</v-icon>
                </v-avatar>
                <div class="flex-grow-1 min-width-0">
                    <div class="d-flex align-center ga-2 flex-wrap">
                        <span class="text-subtitle-1 font-weight-bold">{{ skill.name }}</span>
                        <v-chip v-if="skill.installed" size="x-small" color="success" variant="tonal">Installed</v-chip>
                        <v-chip size="x-small" :color="categoryColor(skill.category)" variant="tonal">{{ skill.category
                            }}</v-chip>
                    </div>
                    <div class="text-caption text-medium-emphasis mt-1">
                        by {{ skill.author }} · v{{ skill.version }} · {{ skill.downloads.toLocaleString() }} downloads
                    </div>
                    <div class="text-body-2 mt-2">{{ skill.description }}</div>
                </div>
                <v-btn icon size="small" variant="text" @click="$emit('update:modelValue', false)">
                    <v-icon size="16">mdi-close</v-icon>
                </v-btn>
            </div>

            <v-divider />

            <!-- 标签页 -->
            <v-tabs v-model="tab" density="compact" class="border-b">
                <v-tab value="overview" class="text-caption">Overview</v-tab>
                <v-tab value="permissions" class="text-caption">Permissions</v-tab>
                <v-tab value="changelog" class="text-caption">Changelog</v-tab>
            </v-tabs>

            <v-card-text class="pa-0" style="max-height:320px;">
                <v-tabs-window v-model="tab">

                    <!-- Overview -->
                    <v-tabs-window-item value="overview">
                        <div class="px-5 py-4">
                            <div
                                class="text-caption text-medium-emphasis mb-3 font-weight-bold text-uppercase tracking-wider">
                                About
                            </div>
                            <p class="text-body-2">{{ skill.longDescription ?? skill.description }}</p>

                            <!-- tags -->
                            <div class="d-flex flex-wrap ga-1 mt-3">
                                <v-chip v-for="tag in skill.tags" :key="tag" size="x-small" variant="outlined">{{ tag
                                    }}</v-chip>
                            </div>

                            <!-- stats row -->
                            <div class="d-flex ga-6 mt-4">
                                <div class="text-center">
                                    <div class="text-subtitle-2 font-weight-bold">{{ skill.rating.toFixed(1) }}</div>
                                    <div class="text-caption text-medium-emphasis">Rating</div>
                                </div>
                                <div class="text-center">
                                    <div class="text-subtitle-2 font-weight-bold">{{ skill.downloads.toLocaleString() }}
                                    </div>
                                    <div class="text-caption text-medium-emphasis">Downloads</div>
                                </div>
                                <div class="text-center">
                                    <div class="text-subtitle-2 font-weight-bold">v{{ skill.version }}</div>
                                    <div class="text-caption text-medium-emphasis">Version</div>
                                </div>
                            </div>
                        </div>
                    </v-tabs-window-item>

                    <!-- Permissions -->
                    <v-tabs-window-item value="permissions">
                        <div class="px-5 py-4">
                            <div v-for="perm in skill.permissions" :key="perm.name"
                                class="perm-item d-flex align-start ga-3 py-2">
                                <v-icon size="16"
                                    :color="perm.level === 'high' ? 'error' : perm.level === 'medium' ? 'warning' : 'success'">
                                    {{ perm.level === 'high' ? 'mdi-shield-alert' : perm.level === 'medium' ?
                                    'mdi-shield-outline' : 'mdi-shield-check' }}
                                </v-icon>
                                <div>
                                    <div class="text-body-2 font-weight-medium">{{ perm.name }}</div>
                                    <div class="text-caption text-medium-emphasis">{{ perm.description }}</div>
                                </div>
                                <v-chip size="x-small"
                                    :color="perm.level === 'high' ? 'error' : perm.level === 'medium' ? 'warning' : 'success'"
                                    variant="tonal" class="ml-auto flex-shrink-0">
                                    {{ perm.level }}
                                </v-chip>
                            </div>
                        </div>
                    </v-tabs-window-item>

                    <!-- Changelog -->
                    <v-tabs-window-item value="changelog">
                        <div class="px-5 py-4">
                            <div v-for="log in skill.changelog" :key="log.version" class="mb-3">
                                <div class="d-flex align-center ga-2 mb-1">
                                    <span class="text-body-2 font-weight-bold">v{{ log.version }}</span>
                                    <span class="text-caption text-disabled">{{ log.date }}</span>
                                </div>
                                <ul class="pl-4">
                                    <li v-for="item in log.items" :key="item" class="text-caption text-medium-emphasis">
                                        {{ item }}</li>
                                </ul>
                            </div>
                        </div>
                    </v-tabs-window-item>

                </v-tabs-window>
            </v-card-text>

            <v-divider />

            <v-card-actions class="px-4 py-3">
                <v-btn v-if="skill.installed" variant="outlined" color="error" size="small"
                    @click="$emit('uninstall', skill)">
                    <v-icon size="12" class="mr-1">mdi-delete-outline</v-icon>Uninstall
                </v-btn>
                <v-spacer />
                <v-btn variant="outlined" size="small" @click="$emit('update:modelValue', false)">Close</v-btn>
                <v-btn v-if="!skill.installed" color="primary" size="small" @click="$emit('install', skill)">
                    <v-icon size="12" class="mr-1">mdi-download</v-icon>Install
                </v-btn>
            </v-card-actions>

        </v-card>
    </v-dialog>
</template>

<script setup lang="ts">
    export interface SkillPermission { name: string; description: string; level: 'low' | 'medium' | 'high' }
    export interface SkillChangelog { version: string; date: string; items: string[] }
    export interface Skill {
        id: number
        name: string
        description: string
        longDescription?: string
        icon: string
        color: string
        category: string
        author: string
        version: string
        rating: number
        downloads: number
        installed: boolean
        tags: string[]
        permissions: SkillPermission[]
        changelog: SkillChangelog[]
    }

    defineProps<{ modelValue: boolean; skill?: Skill | null }>()
    defineEmits<{
        'update:modelValue': [v: boolean]
        install: [skill: Skill]
        uninstall: [skill: Skill]
    }>()

    const tab = ref('overview')

    const categoryColor = (cat: string) => ({
        'Academic': 'primary', 'Productivity': 'success', 'Communication': 'info',
        'Campus Life': 'secondary', 'Research': 'warning',
    }[cat] ?? 'default')
</script>

<style scoped>
    .skill-hero {
        background: rgba(var(--v-theme-surface-variant), 0.3);
    }

    .perm-item {
        border-bottom: 1px solid rgba(var(--v-border-color), 0.08);
    }

    .perm-item:last-child {
        border-bottom: none;
    }

    ul {
        margin: 0;
    }
</style>
