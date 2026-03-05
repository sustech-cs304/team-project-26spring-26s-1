<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0">

        <!-- 头部区域 -->
        <v-sheet class="px-6 py-4 border-b flex-shrink-0" color="transparent">
            <!-- 标题行 -->
            <div class="d-flex align-center ga-3">
                <v-icon size="20" color="primary">mdi-puzzle-outline</v-icon>
                <div>
                    <div class="text-h6 font-weight-bold" style="font-size:18px;line-height:1.3;">Plugin Store</div>
                    <div class="text-caption text-medium-emphasis">Extend your agent with community plugins</div>
                </div>
            </div>
            <!-- 搜索栏 -->
            <div class="position-relative mt-4">
                <v-icon size="16" class="position-absolute text-medium-emphasis"
                    style="top:50%;transform:translateY(-50%);left:12px;z-index:1;">
                    mdi-magnify
                </v-icon>
                <v-text-field v-model="search" density="compact" variant="outlined" placeholder="Search plugins..."
                    hide-details class="store-search" />
            </div>
            <!-- 分类筛选 -->
            <div class="d-flex flex-wrap ga-2 mt-3">
                <button v-for="cat in categories" :key="cat" class="cat-chip"
                    :class="{ 'cat-chip--active': activeCategory === cat }" @click="activeCategory = cat">{{ cat
                    }}</button>
            </div>
        </v-sheet>

        <!-- 插件网格 -->
        <v-sheet color="transparent" class="flex-grow-1 overflow-y-auto">
            <div class="pa-6">
                <v-row>
                    <v-col v-for="plugin in filteredPlugins" :key="plugin.id" cols="12" md="6">
                        <div class="plugin-card" :class="{ 'plugin-card--installed': plugin.installed }">
                            <!-- 头部信息 -->
                            <div class="d-flex align-start ga-3">
                                <div class="plugin-icon-wrap flex-shrink-0">
                                    <v-icon size="20" color="primary">{{ plugin.icon }}</v-icon>
                                </div>
                                <div class="flex-grow-1 min-width-0">
                                    <div class="d-flex align-center flex-wrap ga-1">
                                        <span class="text-body-2 font-weight-bold">{{ plugin.name }}</span>
                                        <v-chip v-if="plugin.installed" variant="outlined" size="x-small"
                                            density="compact" color="primary"
                                            style="font-size:9px;height:18px;border-color:rgba(var(--v-theme-primary),0.3);">
                                            Installed
                                        </v-chip>
                                    </div>
                                    <div class="text-caption text-medium-emphasis mt-1" style="margin-top:2px;">
                                        {{ plugin.author }}
                                    </div>
                                </div>
                            </div>
                            <!-- 描述 -->
                            <div class="text-caption text-medium-emphasis mt-3" style="line-height:1.625;">
                                {{ plugin.description }}
                            </div>
                            <!-- 底部信息栏 -->
                            <div class="d-flex align-center justify-space-between mt-3">
                                <!-- 左侧指标 -->
                                <div class="d-flex align-center ga-3">
                                    <span class="d-flex align-center ga-1">
                                        <v-icon size="12" color="warning">mdi-star</v-icon>
                                        <span class="text-medium-emphasis" style="font-size:10px;">{{ plugin.rating
                                            }}</span>
                                    </span>
                                    <span class="d-flex align-center ga-1">
                                        <v-icon size="12" class="text-medium-emphasis">mdi-download-outline</v-icon>
                                        <span class="text-medium-emphasis" style="font-size:10px;">{{ plugin.downloads
                                            }}</span>
                                    </span>
                                    <v-chip variant="outlined" size="x-small" density="compact"
                                        style="font-size:9px;height:18px;">{{ plugin.category }}</v-chip>
                                </div>
                                <!-- 安装按钮 -->
                                <v-btn :variant="plugin.installed ? 'outlined' : 'elevated'"
                                    :color="plugin.installed ? undefined : 'primary'" size="x-small" height="28"
                                    style="font-size:12px;" @click="toggleInstall(plugin)">
                                    <v-icon :size="12" class="mr-1">{{ plugin.installed ? 'mdi-check' :
                                        'mdi-download-outline' }}</v-icon>
                                    {{ plugin.installed ? 'Installed' : 'Install' }}
                                </v-btn>
                            </div>
                        </div>
                    </v-col>
                </v-row>
                <!-- 空状态 -->
                <div v-if="filteredPlugins.length === 0" class="d-flex flex-column align-center justify-center py-16">
                    <v-icon size="32" style="opacity:0.4;" class="text-medium-emphasis mb-2">mdi-puzzle-outline</v-icon>
                    <span class="text-body-2 text-medium-emphasis">No plugins found</span>
                </div>
            </div>
        </v-sheet>

    </v-container>
</template>

<script setup lang="ts">
    interface Plugin {
        id: number
        name: string
        author: string
        description: string
        icon: string
        rating: number
        downloads: string
        category: string
        installed: boolean
    }

    const search = ref('')
    const activeCategory = ref('All')
    const categories = ['All', 'Academic', 'Productivity', 'Communication', 'Campus Life', 'Research']

    const plugins = ref<Plugin[]>([
        { id: 1, name: 'Blackboard Sync', author: 'SUSTech Dev Team', description: 'Automatically sync course materials, assignments, and grades from Blackboard to your local workspace.', icon: 'mdi-book-open-outline', rating: 4.8, downloads: '12.4k', category: 'Academic', installed: true },
        { id: 2, name: 'Calendar Assistant', author: 'OpenCrab Labs', description: 'Smart calendar integration that syncs academic events, exam schedules, and personal appointments.', icon: 'mdi-calendar-check', rating: 4.6, downloads: '9.8k', category: 'Academic', installed: true },
        { id: 3, name: 'Email Watcher', author: 'community', description: 'Monitor your university email inbox and trigger automations when specific emails arrive.', icon: 'mdi-email-outline', rating: 4.3, downloads: '7.2k', category: 'Communication', installed: false },
        { id: 4, name: 'Code Reviewer', author: 'AI Labs', description: 'Automatically review your code submissions and provide AI-powered feedback before submitting.', icon: 'mdi-code-tags', rating: 4.5, downloads: '5.1k', category: 'Productivity', installed: false },
        { id: 5, name: 'Campus Navigator', author: 'SUSTech Maps', description: 'Real-time campus map integration with seat availability, classroom lookup, and navigation assistance.', icon: 'mdi-map-marker-outline', rating: 4.2, downloads: '8.3k', category: 'Campus Life', installed: false },
        { id: 6, name: 'Research Assistant', author: 'AI Labs', description: 'Connects to academic databases to fetch papers, citations, and summaries relevant to your research topics.', icon: 'mdi-flask-outline', rating: 4.7, downloads: '4.9k', category: 'Research', installed: false },
        { id: 7, name: 'Library Seat Finder', author: 'Campus Tools', description: 'Monitor library seat availability and auto-reserve seats when they become available.', icon: 'mdi-seat', rating: 4.4, downloads: '6.1k', category: 'Campus Life', installed: true },
        { id: 8, name: 'Deadline Tracker', author: 'OpenCrab Labs', description: 'Never miss a deadline. Tracks all course deadlines and sends proactive reminders.', icon: 'mdi-alarm', rating: 4.9, downloads: '15.7k', category: 'Productivity', installed: false },
    ])

    const filteredPlugins = computed(() => plugins.value.filter(p => {
        const matchSearch = !search.value || p.name.toLowerCase().includes(search.value.toLowerCase()) || p.description.toLowerCase().includes(search.value.toLowerCase())
        const matchCat = activeCategory.value === 'All' || p.category === activeCategory.value
        return matchSearch && matchCat
    }))

    const toggleInstall = (plugin: Plugin) => { plugin.installed = !plugin.installed }
</script>

<style scoped>

    /* 搜索框 */
    .store-search :deep(.v-field__input) {
        padding-inline-start: 36px !important;
        font-size: 14px;
    }

    /* 分类芯片 */
    .cat-chip {
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        font-size: 12px;
        font-weight: 500;
        border-radius: 9999px;
        border: none;
        cursor: pointer;
        transition: background 0.15s, color 0.15s;
        background: rgba(var(--v-theme-surface-variant), 0.5);
        color: rgba(var(--v-theme-on-surface), 0.7);
    }

    .cat-chip:hover {
        background: rgba(var(--v-theme-surface-variant), 0.8);
    }

    .cat-chip--active {
        background: rgb(var(--v-theme-primary));
        color: rgb(var(--v-theme-on-primary));
    }

    /* 插件卡片 */
    .plugin-card {
        border-radius: 12px;
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 0;
        transition: background 0.15s, border-color 0.15s;
        height: 100%;
    }

    .plugin-card:hover {
        background: rgba(var(--v-theme-surface-variant), 0.5);
    }

    .plugin-card--installed {
        border-color: rgba(var(--v-theme-primary), 0.2);
        background: rgba(var(--v-theme-primary), 0.03);
    }

    .plugin-card--installed:hover {
        background: rgba(var(--v-theme-primary), 0.06);
    }

    /* 插件图标容器 */
    .plugin-icon-wrap {
        width: 40px;
        height: 40px;
        border-radius: 8px;
        background: rgba(var(--v-theme-primary), 0.1);
        display: flex;
        align-items: center;
        justify-content: center;
    }
</style>
