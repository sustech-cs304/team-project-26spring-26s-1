<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0">

        <!-- 头部 -->
        <v-sheet class="px-6 py-3 border-b flex-shrink-0" color="transparent">
            <div class="d-flex align-center justify-space-between ga-3">
                <div class="d-flex align-center ga-2">
                    <v-icon size="18" color="primary">mdi-puzzle-outline</v-icon>
                    <span class="text-subtitle-2 font-weight-bold">Skills</span>
                    <span class="text-caption text-disabled">({{ filteredSkills.length }})</span>
                </div>
                <v-text-field v-model="search" density="compact" variant="outlined" placeholder="Search skills..."
                    hide-details prepend-inner-icon="mdi-magnify" style="max-width:240px;font-size:12px;" />
            </div>
            <!-- 分类筛选 -->
            <div class="d-flex flex-wrap ga-1 mt-2">
                <v-chip v-for="cat in categories" :key="cat.value" size="small"
                    :variant="activeCategory === cat.value ? 'tonal' : 'text'"
                    :color="activeCategory === cat.value ? 'primary' : undefined" @click="activeCategory = cat.value">
                    {{ cat.label }}
                    <v-badge v-if="cat.value === 'installed'" :content="installedCount" inline color="primary"
                        class="ml-1" />
                </v-chip>
            </div>
        </v-sheet>

        <!-- 技能网格 -->
        <v-sheet color="transparent" class="flex-grow-1 overflow-y-auto">
            <div class="pa-4">
                <div v-if="filteredSkills.length === 0" class="d-flex flex-column align-center justify-center py-16">
                    <v-icon size="32" style="opacity:.35;" class="text-medium-emphasis mb-1">mdi-puzzle-outline</v-icon>
                    <span class="text-body-2 text-medium-emphasis mt-1">No skills found</span>
                </div>
                <v-row v-else dense>
                    <v-col v-for="skill in filteredSkills" :key="skill.id" cols="12" sm="6" lg="4">
                        <v-card variant="outlined" rounded="lg" class="pa-3"
                            :color="skill.installed ? 'success' : undefined"
                            :style="skill.installed ? { borderColor: 'rgba(var(--v-theme-success), 0.35)', background: 'rgba(var(--v-theme-success), 0.025)' } : {}"
                            style="cursor:pointer;" @click="openDetail(skill)">
                            <div class="d-flex align-start ga-3">
                                <v-avatar :color="skill.color" rounded="md" size="36">
                                    <v-icon :size="18" color="white">{{ skill.icon }}</v-icon>
                                </v-avatar>
                                <div class="flex-grow-1 min-width-0">
                                    <div class="d-flex align-center ga-1 flex-wrap">
                                        <span class="text-body-2 font-weight-bold text-truncate">{{ skill.name }}</span>
                                        <v-chip v-if="skill.installed" size="x-small" color="success" variant="tonal"
                                            style="font-size:9px;height:16px;"> Installed</v-chip>
                                    </div>
                                    <div class="text-caption text-disabled" style="font-size:10px;">
                                        {{ skill.author }} v{{ skill.version }}
                                    </div>
                                </div>
                                <v-btn icon size="x-small" variant="tonal"
                                    :color="skill.installed ? 'error' : 'primary'" @click.stop="toggleInstall(skill)">
                                    <v-icon size="13">{{ skill.installed ? 'mdi-delete-outline' : 'mdi-download'
                                        }}</v-icon>
                                    <v-tooltip activator="parent" location="top">{{ skill.installed ? 'Uninstall' :
                                        'Install' }}</v-tooltip>
                                </v-btn>
                            </div>
                            <div class="text-caption text-medium-emphasis mt-2 skill-desc"
                                style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;line-height:1.5;">
                                {{ skill.description }}</div>
                            <div class="d-flex align-center justify-space-between mt-2">
                                <div class="d-flex ga-1 flex-wrap">
                                    <v-chip v-for="tag in skill.tags.slice(0, 2)" :key="tag" size="x-small"
                                        variant="outlined" density="compact" style="font-size:9px;height:16px;">{{ tag
                                        }}</v-chip>
                                </div>
                                <div class="d-flex align-center ga-1">
                                    <v-icon size="11" color="warning">mdi-star</v-icon>
                                    <span class="text-caption" style="font-size:10px;">{{ skill.rating.toFixed(1)
                                        }}</span>
                                    <span class="text-caption text-disabled" style="font-size:10px;"> {{
                                        fmtNum(skill.downloads) }}</span>
                                </div>
                            </div>
                        </v-card>
                    </v-col>
                </v-row>
            </div>
        </v-sheet>

        <!-- 详情弹窗 -->
        <SkillDetailDialog v-model="detailOpen" :skill="selectedSkill"
            @install="s => { s.installed = true; detailOpen = false }"
            @uninstall="s => { s.installed = false; detailOpen = false }" />

    </v-container>
</template>

<script setup lang="ts">
    import SkillDetailDialog from '@/components/tasks/SkillDetailDialog.vue'
    import type { Skill } from '@/components/tasks/SkillDetailDialog.vue'

    //  Mock Data 
    const skills = ref<Skill[]>([
        {
            id: 1, name: 'Course Schedule Sync', icon: 'mdi-calendar-sync', color: '#1976D2',
            category: 'Academic', author: 'SUSTech Labs', version: '2.1.0',
            rating: 4.8, downloads: 12400, installed: true,
            description: 'Sync your SUSTech course schedule to the calendar automatically.',
            longDescription: 'Automatically fetches your course schedule from SUSTech portal and syncs it to the built-in calendar. Supports semester switching, custom reminders, and conflict detection.',
            tags: ['schedule', 'sync', 'calendar'],
            permissions: [
                { name: 'Calendar Write', description: 'Create and update calendar events', level: 'medium' },
                { name: 'Network Access', description: 'Access SUSTech portal APIs', level: 'low' },
            ],
            changelog: [
                { version: '2.1.0', date: '2026-02-01', items: ['Add semester switch support', 'Fix timezone issues'] },
                { version: '2.0.0', date: '2026-01-01', items: ['Complete rewrite with new API', 'Dark mode support'] },
            ],
        },
        {
            id: 2, name: 'Assignment Tracker', icon: 'mdi-clipboard-check-outline', color: '#388E3C',
            category: 'Academic', author: 'EdTech Community', version: '1.5.2',
            rating: 4.5, downloads: 8900, installed: true,
            description: 'Track all your assignments, deadlines and submission status in one place.',
            longDescription: 'A comprehensive assignment management tool that integrates with common learning management systems. Set reminders, track progress, and never miss a deadline again.',
            tags: ['assignments', 'deadline', 'tracker'],
            permissions: [
                { name: 'Task Create', description: 'Create tasks in the task manager', level: 'low' },
                { name: 'Notification Send', description: 'Send desktop notifications', level: 'low' },
            ],
            changelog: [
                { version: '1.5.2', date: '2026-01-15', items: ['Fix LMS integration bug', 'Improve reminder accuracy'] },
                { version: '1.5.0', date: '2025-12-01', items: ['Add Blackboard integration', 'Batch import assignments'] },
            ],
        },
        {
            id: 3, name: 'Research Paper Assistant', icon: 'mdi-file-document-edit-outline', color: '#7B1FA2',
            category: 'Research', author: 'AI Research Group', version: '3.0.1',
            rating: 4.9, downloads: 22000, installed: false,
            description: 'AI-powered tool to summarize papers, extract key insights and manage citations.',
            longDescription: 'Leverages large language models to help you read, summarize, and organize academic papers. Supports BibTeX export, citation network visualization, and cross-paper comparison.',
            tags: ['research', 'papers', 'AI', 'citations'],
            permissions: [
                { name: 'File System Read', description: 'Read PDF files from your computer', level: 'medium' },
                { name: 'AI Model Access', description: 'Use the configured LLM for summarization', level: 'high' },
                { name: 'Network Access', description: 'Access Arxiv and Semantic Scholar APIs', level: 'low' },
            ],
            changelog: [
                { version: '3.0.1', date: '2026-02-20', items: ['Fix PDF parsing for scanned papers', 'Add GPT-4 support'] },
                { version: '3.0.0', date: '2026-01-10', items: ['Redesigned UI', 'Citation graph feature', 'BibTeX export'] },
            ],
        },
        {
            id: 4, name: 'Smart Meeting Notes', icon: 'mdi-microphone-outline', color: '#F57C00',
            category: 'Productivity', author: 'MeetingAI', version: '1.2.0',
            rating: 4.3, downloads: 5600, installed: false,
            description: 'Record, transcribe and summarize meeting notes with AI assistance.',
            longDescription: 'Records audio during meetings, transcribes speech to text in real-time, and uses AI to generate concise summaries with action items automatically extracted.',
            tags: ['meeting', 'transcription', 'notes'],
            permissions: [
                { name: 'Microphone Access', description: 'Record audio from microphone', level: 'high' },
                { name: 'File System Write', description: 'Save transcripts and notes', level: 'medium' },
                { name: 'AI Model Access', description: 'Use LLM for summarization', level: 'high' },
            ],
            changelog: [
                { version: '1.2.0', date: '2026-02-10', items: ['Real-time transcription', 'Action item extraction'] },
                { version: '1.0.0', date: '2025-11-01', items: ['Initial release'] },
            ],
        },
        {
            id: 5, name: 'Campus Navigator', icon: 'mdi-map-marker-outline', color: '#00796B',
            category: 'Campus Life', author: 'SUSTech Open Source', version: '1.0.5',
            rating: 4.1, downloads: 3200, installed: false,
            description: 'Navigate SUSTech campus with indoor maps, building info and shuttle schedules.',
            longDescription: 'Features indoor floor plans for all major buildings, real-time shuttle bus schedules, canteen menus, and points of interest on campus.',
            tags: ['campus', 'map', 'navigation'],
            permissions: [
                { name: 'Location Access', description: 'Access device location for navigation', level: 'medium' },
                { name: 'Network Access', description: 'Fetch real-time shuttle data', level: 'low' },
            ],
            changelog: [
                { version: '1.0.5', date: '2026-01-20', items: ['Updated shuttle schedule API', 'Add new canteen'] },
            ],
        },
        {
            id: 6, name: 'Study Group Finder', icon: 'mdi-account-group-outline', color: '#C62828',
            category: 'Communication', author: 'Social Learning Lab', version: '2.3.0',
            rating: 4.6, downloads: 7100, installed: false,
            description: 'Find and create study groups for your courses, schedule sessions and collaborate.',
            longDescription: 'Connects students taking the same courses to form study groups. Features session scheduling, shared notes, and integrated video calling.',
            tags: ['study group', 'collaboration', 'social'],
            permissions: [
                { name: 'Profile Access', description: 'Access your academic profile', level: 'medium' },
                { name: 'Network Access', description: 'Connect to study group server', level: 'low' },
            ],
            changelog: [
                { version: '2.3.0', date: '2026-02-15', items: ['Add video call integration', 'Shared whiteboard'] },
            ],
        },
        {
            id: 7, name: 'Grade Calculator', icon: 'mdi-calculator-variant-outline', color: '#1565C0',
            category: 'Academic', author: 'AcadTools', version: '1.1.0',
            rating: 4.4, downloads: 9800, installed: false,
            description: 'Calculate GPA, predict final grades, and plan your academic performance.',
            longDescription: 'Input your current grades and course weights to predict your semester GPA. Simulate different score scenarios to understand what you need to achieve your target.',
            tags: ['GPA', 'grades', 'calculator'],
            permissions: [
                { name: 'Storage', description: 'Store grade data locally', level: 'low' },
            ],
            changelog: [
                { version: '1.1.0', date: '2026-01-05', items: ['Add weighted GPA mode', 'Export to CSV'] },
            ],
        },
        {
            id: 8, name: 'Focus Timer', icon: 'mdi-timer-outline', color: '#558B2F',
            category: 'Productivity', author: 'DeepWork Studio', version: '1.4.0',
            rating: 4.7, downloads: 15000, installed: true,
            description: 'Pomodoro-based focus timer with distraction blocking and session analytics.',
            longDescription: 'Implements the Pomodoro technique with customizable work/break intervals. Blocks distracting websites during focus sessions and provides detailed productivity analytics.',
            tags: ['focus', 'pomodoro', 'productivity'],
            permissions: [
                { name: 'Notification Send', description: 'Timer alerts and break reminders', level: 'low' },
                { name: 'System Integration', description: 'Website blocking during focus sessions', level: 'high' },
            ],
            changelog: [
                { version: '1.4.0', date: '2026-02-01', items: ['Analytics dashboard', 'Custom sound themes'] },
            ],
        },
    ])

    const categories = [
        { value: 'all', label: 'All' },
        { value: 'Academic', label: 'Academic' },
        { value: 'Productivity', label: 'Productivity' },
        { value: 'Research', label: 'Research' },
        { value: 'Communication', label: 'Communication' },
        { value: 'Campus Life', label: 'Campus Life' },
        { value: 'installed', label: ' Installed' },
    ]

    const search = ref('')
    const activeCategory = ref('all')

    const installedCount = computed(() => skills.value.filter(s => s.installed).length)

    const filteredSkills = computed(() => skills.value.filter(s => {
        const q = search.value.toLowerCase()
        const matchQ = !q || s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q) || s.tags.some(t => t.includes(q))
        const matchCat = activeCategory.value === 'all'
            ? true
            : activeCategory.value === 'installed'
                ? s.installed
                : s.category === activeCategory.value
        return matchQ && matchCat
    }))

    const detailOpen = ref(false)
    const selectedSkill = ref<Skill | null>(null)

    const openDetail = (s: Skill) => { selectedSkill.value = s; detailOpen.value = true }

    const toggleInstall = (s: Skill) => { s.installed = !s.installed }

    const fmtNum = (n: number) => n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n)
</script>

<style scoped>
    /* 无需自定义 CSS，所有样式已由 Vuetify 组件 props 实现 */
</style>
