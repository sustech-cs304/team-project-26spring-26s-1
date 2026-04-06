<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0">

        <!-- 头部 -->
        <v-sheet class="px-6 py-4 border-b flex-shrink-0" color="transparent">
            <div class="d-flex align-center ga-3">
                <v-icon size="20" color="primary">mdi-cog-outline</v-icon>
                <div>
                    <div class="text-h6 font-weight-bold" style="font-size:18px;line-height:1.3;">Global Settings</div>
                    <div class="text-caption text-medium-emphasis">Configure all infrastructure for your AI Agent</div>
                </div>
            </div>
        </v-sheet>

        <!-- 左右分栏 -->
        <div class="d-flex flex-grow-1 overflow-hidden">

            <!-- 左侧标签导航 -->
            <v-sheet class="flex-shrink-0 overflow-y-auto border-e" color="transparent" width="220">
                <v-list density="compact" class="pa-2" nav>
                    <v-list-item v-for="tab in tabs" :key="tab.id" :prepend-icon="tab.icon" :title="tab.label"
                        :active="activeTab === tab.id" active-color="primary" rounded="lg"
                        :append-icon="activeTab === tab.id ? 'mdi-chevron-right' : undefined"
                        @click="activeTab = tab.id" />
                </v-list>
            </v-sheet>

            <!-- 右侧内容区 -->
            <v-sheet color="transparent" class="flex-grow-1 overflow-y-auto">
                <div class="pa-6" style="max-width:672px;margin:0 auto;">

                    <!-- LLM Configuration -->
                    <div v-if="activeTab === 'llm'">
                        <div class="text-subtitle-1 font-weight-bold mb-1">LLM Configuration</div>
                        <div class="text-caption text-medium-emphasis mb-6" style="line-height:1.625;">
                            Configure the language model API used by your AI Agent. Supports OpenAI-compatible
                            endpoints.
                        </div>

                        <!-- API Provider -->
                        <div class="mb-5">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-2">API Provider</div>
                            <v-btn-toggle v-model="llm.provider" mandatory density="compact" variant="outlined"
                                color="primary">
                                <v-btn v-for="p in apiProviders" :key="p" :value="p" size="small">{{ p }}</v-btn>
                            </v-btn-toggle>
                        </div>

                        <!-- API Key -->
                        <div class="mb-5">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-2">API Key</div>
                            <div class="position-relative">
                                <v-text-field v-model="llm.apiKey" density="compact" variant="outlined"
                                    :type="showApiKey ? 'text' : 'password'" hide-details
                                    style="font-family:monospace;font-size:14px;" class="pr-10" />
                                <v-btn icon variant="text" size="x-small" class="position-absolute"
                                    style="right:8px;top:50%;transform:translateY(-50%);"
                                    @click="showApiKey = !showApiKey">
                                    <v-icon size="16" class="text-medium-emphasis">{{ showApiKey ? 'mdi-eye-off' :
                                        'mdi-eye' }}</v-icon>
                                </v-btn>
                            </div>
                        </div>

                        <!-- Base URL -->
                        <div class="mb-5">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-2">Base URL</div>
                            <v-text-field v-model="llm.baseUrl" density="compact" variant="outlined" hide-details
                                style="font-family:monospace;font-size:14px;" />
                            <div class="text-medium-emphasis mt-1" style="font-size:11px;">
                                Supports reverse proxy or custom relay endpoints.
                            </div>
                        </div>

                        <!-- 连接测试 -->
                        <div class="d-flex align-center ga-3 mb-5">
                            <v-btn size="small" variant="outlined" :loading="llm.testing" @click="testConnection">
                                <v-icon v-if="llm.testing" size="14" class="spin-icon mr-1">mdi-loading</v-icon>
                                Test Connection
                            </v-btn>
                            <div v-if="llm.testResult === 'success'" class="d-flex align-center ga-1">
                                <v-icon size="16" color="success">mdi-check-circle</v-icon>
                                <span class="text-caption font-weight-bold text-success">Connection successful</span>
                            </div>
                            <div v-else-if="llm.testResult === 'failed'" class="d-flex align-center ga-1">
                                <v-icon size="16" color="error">mdi-close-circle</v-icon>
                                <span class="text-caption font-weight-bold text-error">Connection failed - check your
                                    credentials</span>
                            </div>
                        </div>

                        <v-divider class="mb-4" />
                        <v-btn size="small" color="primary" @click="">Save Configuration</v-btn>
                    </div>

                    <!-- Credential Vault -->
                    <div v-else-if="activeTab === 'credentials'">
                        <div class="text-subtitle-1 font-weight-bold mb-1">Credential Vault</div>
                        <div class="text-caption text-medium-emphasis mb-4" style="line-height:1.625;">
                            Securely store and manage your SUSTech authentication credentials.
                        </div>

                        <!-- 安全提示 -->
                        <v-alert type="success" variant="tonal" density="compact" class="mb-5" style="font-size:12px;">
                            All credentials are encrypted locally using AES-256 and never transmitted to external
                            servers.
                        </v-alert>

                        <!-- 认证方式 -->
                        <div class="mb-5">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-2">Authentication Method
                            </div>
                            <v-btn-toggle v-model="creds.method" mandatory density="compact" variant="outlined"
                                color="primary">
                                <v-btn v-for="m in authMethods" :key="m.value" :value="m.value" size="small">{{ m.label
                                }}</v-btn>
                            </v-btn-toggle>
                        </div>

                        <!-- CAS Login 表单 -->
                        <template v-if="creds.method === 'cas'">
                            <div class="mb-4">
                                <div class="text-caption text-medium-emphasis mb-1">Student ID</div>
                                <v-text-field v-model="creds.studentId" density="compact" variant="outlined"
                                    placeholder="e.g. 12110001" hide-details style="font-family:monospace;" />
                            </div>
                            <div class="mb-5">
                                <div class="text-caption text-medium-emphasis mb-1">Password</div>
                                <div class="position-relative">
                                    <v-text-field v-model="creds.password" density="compact" variant="outlined"
                                        :type="showPassword ? 'text' : 'password'" hide-details />
                                    <v-btn icon variant="text" size="x-small" class="position-absolute"
                                        style="right:8px;top:50%;transform:translateY(-50%);"
                                        @click="showPassword = !showPassword">
                                        <v-icon size="16" class="text-medium-emphasis">{{ showPassword ? 'mdi-eye-off' :
                                            'mdi-eye' }}</v-icon>
                                    </v-btn>
                                </div>
                            </div>
                        </template>

                        <!-- Session Cookie 表单 -->
                        <template v-else>
                            <div class="mb-5">
                                <div class="text-caption text-medium-emphasis mb-1">Session Cookie</div>
                                <v-text-field v-model="creds.cookie" density="compact" variant="outlined" hide-details
                                    style="font-family:monospace;" />
                                <div class="text-medium-emphasis mt-1" style="font-size:11px;">
                                    For advanced users: paste the session cookie directly to bypass CAPTCHA
                                    verification.
                                </div>
                            </div>
                        </template>

                        <v-divider class="mb-4" />
                        <v-btn size="small" color="primary" @click="">Save Credentials</v-btn>
                    </div>

                    <!-- System Preferences -->
                    <div v-else-if="activeTab === 'preferences'">
                        <div class="text-subtitle-1 font-weight-bold mb-1">System Preferences</div>
                        <div class="text-caption text-medium-emphasis mb-6">Configure system-level behavior of the
                            agent.</div>

                        <!-- 唤醒快捷键 -->
                        <div class="mb-5">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-2">Wake Shortcut</div>
                            <div class="d-flex align-center ga-2">
                                <div class="shortcut-display flex-grow-1"
                                    :class="{ 'shortcut-display--recording': prefs.recording }">
                                    <v-icon size="14" class="text-medium-emphasis mr-2">mdi-keyboard-outline</v-icon>
                                    <span v-if="prefs.recording" class="recording-text">Press a key
                                        combination...</span>
                                    <span v-else>{{ prefs.shortcut }}</span>
                                </div>
                                <v-btn variant="outlined" size="small" style="font-size:12px;"
                                    :disabled="prefs.recording" @click="startRecording">
                                    {{ prefs.recording ? 'Recording...' : 'Record' }}
                                </v-btn>
                            </div>
                        </div>

                        <!-- 开机自启动 -->
                        <v-card variant="outlined" rounded="lg" class="pa-3 mb-5" max-width="420">
                            <div class="d-flex align-center ga-3">
                                <v-icon size="16" class="text-medium-emphasis">mdi-power</v-icon>
                                <div class="flex-grow-1">
                                    <div class="text-body-large font-weight-medium">Launch on Startup</div>
                                    <div class="text-medium-emphasis" style="font-size:11px;">
                                        Automatically start Agent when system boots
                                    </div>
                                </div>
                                <v-switch v-model="prefs.startup" density="compact" hide-details color="primary" />
                            </div>
                        </v-card>

                        <!-- 工作区路径 -->
                        <div class="mb-5">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-2">Default Workspace
                                Path</div>
                            <div class="d-flex ga-2">
                                <v-text-field v-model="prefs.workspacePath" density="compact" variant="outlined"
                                    hide-details style="font-family:monospace;font-size:14px;" class="flex-grow-1" />
                                <v-btn variant="outlined" size="small" style="font-size:12px;">
                                    <v-icon size="14" class="mr-1">mdi-folder-outline</v-icon>
                                    Browse
                                </v-btn>
                            </div>
                            <div class="text-medium-emphasis mt-1" style="font-size:11px;">
                                Agent will organize files, download courseware, and store data in this directory.
                            </div>
                        </div>

                        <v-divider class="mb-4" />
                        <v-btn size="small" color="primary" @click="">Save Preferences</v-btn>
                    </div>

                    <!-- Appearance -->
                    <div v-else-if="activeTab === 'appearance'">
                        <div class="text-subtitle-1 font-weight-bold mb-1">Appearance</div>
                        <div class="text-caption text-medium-emphasis mb-6">Customize the look and feel of the
                            application.</div>

                        <!-- Theme -->
                        <div class="mb-5">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-2">Theme</div>
                            <v-btn-toggle v-model="appearance.theme" mandatory density="compact" variant="outlined"
                                color="primary">
                                <v-btn v-for="t in themeOptions" :key="t.value" :value="t.value" size="small">
                                    <v-icon :size="13" class="mr-1">{{ t.icon }}</v-icon>{{ t.label }}
                                </v-btn>
                            </v-btn-toggle>
                            <div class="text-medium-emphasis mt-1" style="font-size:11px;">
                                System mode follows your OS appearance settings.
                            </div>
                        </div>

                        <!-- Language -->
                        <div class="mb-5">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-2">Language</div>
                            <v-select v-model="appearance.language" :items="languageOptions" item-title="label"
                                item-value="value" density="compact" variant="outlined" hide-details
                                style="max-width:260px;" />
                        </div>

                        <!-- Font Size -->
                        <div class="mb-5">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-2">
                                UI Font Size — <span class="text-primary font-weight-bold">{{ appearance.fontSize
                                    }}px</span>
                            </div>
                            <v-slider v-model="appearance.fontSize" :min="11" :max="16" :step="1" density="compact"
                                hide-details thumb-label color="primary" style="max-width:320px;" />
                        </div>

                        <!-- Compact Mode -->
                        <v-card variant="outlined" rounded="lg" class="pa-3 mb-5" max-width="420">
                            <div class="d-flex align-center ga-3">
                                <v-icon size="16" class="text-medium-emphasis">mdi-arrow-collapse-all</v-icon>
                                <div class="flex-grow-1">
                                    <div class="text-body-large font-weight-medium">Compact Mode</div>
                                    <div class="text-medium-emphasis" style="font-size:11px;">
                                        Reduce padding and spacing for a denser layout
                                    </div>
                                </div>
                                <v-switch v-model="appearance.compact" density="compact" hide-details color="primary" />
                            </div>
                        </v-card>

                        <v-divider class="mb-4" />
                        <v-btn size="small" color="primary">Save Appearance</v-btn>
                    </div>

                    <!-- Window -->
                    <div v-else-if="activeTab === 'window'">
                        <div class="text-subtitle-1 font-weight-bold mb-1">Window</div>
                        <div class="text-caption text-medium-emphasis mb-6">Control how the application window behaves
                            (Tauri desktop).
                        </div>

                        <!-- Always on Top -->
                        <v-card variant="outlined" rounded="lg" class="pa-3 mb-3" max-width="420">
                            <div class="d-flex align-center ga-3">
                                <v-icon size="16" class="text-medium-emphasis">mdi-pin-outline</v-icon>
                                <div class="flex-grow-1">
                                    <div class="text-body-large font-weight-medium">Always on Top</div>
                                    <div class="text-medium-emphasis" style="font-size:11px;">Keep window above all
                                        other application windows</div>
                                </div>
                                <v-switch v-model="winSettings.alwaysOnTop" density="compact" hide-details
                                    color="primary" @update:model-value="applyAlwaysOnTop" />
                            </div>
                        </v-card>

                        <!-- Minimize to Tray -->
                        <v-card variant="outlined" rounded="lg" class="pa-3 mb-3" max-width="420">
                            <div class="d-flex align-center ga-3">
                                <v-icon size="16" class="text-medium-emphasis">mdi-tray-arrow-down</v-icon>
                                <div class="flex-grow-1">
                                    <div class="text-body-large font-weight-medium">Minimize to System Tray</div>
                                    <div class="text-medium-emphasis" style="font-size:11px;">Closing the window hides
                                        to tray instead of quitting</div>
                                </div>
                                <v-switch v-model="winSettings.minimizeToTray" density="compact" hide-details
                                    color="primary" />
                            </div>
                        </v-card>

                        <!-- Start Minimized -->
                        <v-card variant="outlined" rounded="lg" class="pa-3 mb-5" max-width="420">
                            <div class="d-flex align-center ga-3">
                                <v-icon size="16" class="text-medium-emphasis">mdi-window-minimize</v-icon>
                                <div class="flex-grow-1">
                                    <div class="text-body-large font-weight-medium">Start Minimized</div>
                                    <div class="text-medium-emphasis" style="font-size:11px;">Launch in background
                                        without showing the window</div>
                                </div>
                                <v-switch v-model="winSettings.startMinimized" density="compact" hide-details
                                    color="primary" />
                            </div>
                        </v-card>

                        <!-- Window Opacity -->
                        <div class="mb-5">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-2">
                                Window Opacity — <span class="text-primary font-weight-bold">{{ winSettings.opacity
                                    }}%</span>
                            </div>
                            <v-slider v-model="winSettings.opacity" :min="60" :max="100" :step="5" density="compact"
                                hide-details thumb-label color="primary" style="max-width:320px;" />
                        </div>

                        <v-divider class="mb-4" />
                        <v-btn size="small" color="primary">Apply Window Settings</v-btn>
                    </div>

                    <!-- Notifications -->
                    <div v-else-if="activeTab === 'notifications'">
                        <div class="text-subtitle-1 font-weight-bold mb-1">Notifications</div>
                        <div class="text-caption text-medium-emphasis mb-6">Control when and how you receive
                            notifications.</div>

                        <!-- Master Switch -->
                        <v-card variant="outlined" rounded="lg" class="pa-3 mb-4" max-width="420">
                            <div class="d-flex align-center ga-3">
                                <v-icon size="16" :color="notif.enabled ? 'primary' : undefined"
                                    class="text-medium-emphasis">mdi-bell-outline</v-icon>
                                <div class="flex-grow-1">
                                    <div class="text-body-large font-weight-medium">Enable Notifications</div>
                                    <div class="text-medium-emphasis" style="font-size:11px;">Master toggle for all
                                        notification types</div>
                                </div>
                                <v-switch v-model="notif.enabled" density="compact" hide-details color="primary" />
                            </div>
                        </v-card>

                        <div :class="{ 'opacity-40': !notif.enabled }" style="pointer-events: var(--notif-events);"
                            :style="{ pointerEvents: notif.enabled ? 'auto' : 'none' }">
                            <v-card v-for="item in notifItems" :key="item.key" variant="outlined" rounded="lg"
                                class="pa-3 mb-3" max-width="420">
                                <div class="d-flex align-center ga-3">
                                    <v-icon size="16" class="text-medium-emphasis">{{ item.icon }}</v-icon>
                                    <div class="flex-grow-1">
                                        <div class="text-body-large font-weight-medium">{{ item.label }}</div>
                                        <div class="text-medium-emphasis" style="font-size:11px;">{{ item.desc }}</div>
                                    </div>
                                    <v-switch v-model="(notif as any)[item.key]" density="compact" hide-details
                                        color="primary" />
                                </div>
                            </v-card>
                        </div>

                        <v-divider class="mb-4 mt-2" />
                        <v-btn size="small" color="primary">Save Notification Settings</v-btn>
                    </div>

                    <!-- Capability Hub -->
                    <div v-else-if="activeTab === 'capabilities'">
                        <div class="d-flex align-center justify-space-between mb-1">
                            <div class="text-subtitle-1 font-weight-bold">Capability Hub</div>
                            <v-chip variant="outlined" size="x-small" density="compact" color="primary"
                                style="font-size:10px;">
                                {{capabilities.filter(c => c.enabled).length}}/{{ capabilities.length }} active
                            </v-chip>
                        </div>
                        <div class="text-caption text-medium-emphasis mb-6" style="line-height:1.625;">
                            Manage all detected .py plugins and their permissions. Toggle capabilities to control agent
                            behavior.
                        </div>

                        <div class="d-flex flex-column ga-2">
                            <v-card v-for="cap in capabilities" :key="cap.id"
                                :color="cap.enabled ? 'primary' : undefined"
                                :variant="cap.enabled ? 'tonal' : 'outlined'" rounded="lg">
                                <!-- 折叠态 -->
                                <div class="d-flex align-center ga-3 px-4 py-3">
                                    <v-btn icon variant="text" size="x-small" @click="cap.expanded = !cap.expanded">
                                        <v-icon size="14" class="text-medium-emphasis"
                                            :style="cap.expanded ? 'transform:rotate(180deg)' : ''">
                                            mdi-chevron-down
                                        </v-icon>
                                    </v-btn>
                                    <div class="flex-grow-1 min-width-0">
                                        <div class="d-flex align-center ga-2">
                                            <span class="text-body-large font-weight-medium">{{ cap.name }}</span>
                                            <code class="text-medium-emphasis"
                                                style="font-size:10px;">{{ cap.filename }}</code>
                                        </div>
                                        <div class="text-medium-emphasis mt-1" style="font-size:11px;">{{
                                            cap.description }}</div>
                                    </div>
                                    <v-switch v-model="cap.enabled" density="compact" hide-details color="primary" />
                                </div>
                                <!-- 展开态 -->
                                <template v-if="cap.expanded">
                                    <v-divider />
                                    <div class="px-4 py-3">
                                        <div class="d-flex align-center ga-1 mb-2">
                                            <v-icon size="14"
                                                class="text-medium-emphasis">mdi-information-outline</v-icon>
                                            <span class="text-caption font-weight-bold text-medium-emphasis">Required
                                                Permissions</span>
                                        </div>
                                        <div class="d-flex flex-column ga-1 pl-5">
                                            <div v-for="perm in cap.permissions" :key="perm"
                                                class="d-flex align-center ga-2">
                                                <v-icon size="6" :color="cap.enabled ? 'primary' : undefined"
                                                    style="opacity:0.7;">mdi-circle</v-icon>
                                                <span style="font-size:11px;" class="text-medium-emphasis">{{ perm
                                                }}</span>
                                            </div>
                                        </div>
                                    </div>
                                </template>
                            </v-card>
                        </div>
                    </div>

                </div>
            </v-sheet>
        </div>

    </v-container>
</template>

<script setup lang="ts">
    const activeTab = ref('llm')

    const tabs = [
        { id: 'llm', icon: 'mdi-brain', label: 'LLM Configuration' },
        { id: 'credentials', icon: 'mdi-shield-check', label: 'Credential Vault' },
        { id: 'appearance', icon: 'mdi-palette-outline', label: 'Appearance' },
        { id: 'window', icon: 'mdi-application-outline', label: 'Window' },
        { id: 'notifications', icon: 'mdi-bell-outline', label: 'Notifications' },
        { id: 'preferences', icon: 'mdi-wrench-outline', label: 'System Preferences' },
        { id: 'capabilities', icon: 'mdi-puzzle-outline', label: 'Capability Hub' },
    ]

    // LLM
    const apiProviders = ['OpenAI', 'DeepSeek', 'Local Ollama']
    const showApiKey = ref(false)
    const llm = ref({
        provider: 'OpenAI',
        apiKey: '',
        baseUrl: 'https://api.openai.com/v1',
        testing: false,
        testResult: '' as '' | 'success' | 'failed',
    })

    const testConnection = async () => {
        llm.value.testing = true
        llm.value.testResult = ''
        await new Promise(r => setTimeout(r, 1500))
        llm.value.testing = false
        llm.value.testResult = llm.value.apiKey.length > 5 ? 'success' : 'failed'
    }

    // Credentials
    const showPassword = ref(false)
    const authMethods = [
        { value: 'cas', label: 'SUSTech CAS Login' },
        { value: 'cookie', label: 'Session Cookie' },
    ]
    const creds = ref({ method: 'cas', studentId: '', password: '', cookie: '' })

    // Preferences
    const prefs = ref({ shortcut: 'Alt + Space', recording: false, startup: true, workspacePath: '~/Documents/OpenCrab' })
    let recordTimer: ReturnType<typeof setTimeout>
    const startRecording = () => {
        prefs.value.recording = true
        const handler = (e: KeyboardEvent) => {
            e.preventDefault()
            const parts: string[] = []
            if (e.ctrlKey) parts.push('Ctrl')
            if (e.altKey) parts.push('Alt')
            if (e.shiftKey) parts.push('Shift')
            if (e.metaKey) parts.push('Meta')
            if (e.key && !['Control', 'Alt', 'Shift', 'Meta'].includes(e.key))
                parts.push(e.key.toUpperCase())
            if (parts.length > 1) {
                prefs.value.shortcut = parts.join(' + ')
                prefs.value.recording = false
                window.removeEventListener('keydown', handler)
                clearTimeout(recordTimer)
            }
        }
        window.addEventListener('keydown', handler)
        recordTimer = setTimeout(() => {
            prefs.value.recording = false
            window.removeEventListener('keydown', handler)
        }, 5000)
    }

    // Capabilities
    const capabilities = ref([
        { id: 1, name: 'Web Search', filename: 'web_search.py', description: 'Search the internet for real-time information.', enabled: true, expanded: false, permissions: ['Network access', 'External API calls', 'Response caching'] },
        { id: 2, name: 'File Manager', filename: 'file_manager.py', description: 'Read, write, and organize files in the workspace.', enabled: true, expanded: false, permissions: ['File system read', 'File system write', 'Directory listing'] },
        { id: 3, name: 'Email Sender', filename: 'email_sender.py', description: 'Send emails on behalf of the user.', enabled: false, expanded: false, permissions: ['SMTP access', 'Contact list read', 'Email compose'] },
        { id: 4, name: 'Calendar Sync', filename: 'calendar_sync.py', description: 'Read and write calendar events.', enabled: true, expanded: false, permissions: ['Calendar read', 'Calendar write', 'External calendar API'] },
    ])

    // Appearance
    const themeOptions = [
        { value: 'system', label: 'System', icon: 'mdi-monitor' },
        { value: 'light', label: 'Light', icon: 'mdi-white-balance-sunny' },
        { value: 'dark', label: 'Dark', icon: 'mdi-weather-night' },
    ]
    const languageOptions = [
        { value: 'en', label: 'English' },
        { value: 'zh', label: '中文 (简体)' },
        { value: 'zh-tw', label: '中文 (繁體)' },
        { value: 'ja', label: '日本語' },
    ]
    const appearance = ref({ theme: 'system', language: 'en', fontSize: 13, compact: true })

    // Window (Tauri)
    const winSettings = ref({ alwaysOnTop: false, minimizeToTray: true, startMinimized: false, opacity: 100 })

    const toggleAlwaysOnTop = async () => {
        winSettings.value.alwaysOnTop = !winSettings.value.alwaysOnTop
        await applyAlwaysOnTop(winSettings.value.alwaysOnTop)
    }

    const applyAlwaysOnTop = async (val: boolean | null) => {
        const v = val ?? false
        try {
            const { getCurrentWindow } = await import('@tauri-apps/api/window')
            await getCurrentWindow().setAlwaysOnTop(v)
        } catch { /* web fallback: ignore */ }
    }

    // Notifications
    const notif = ref({ enabled: true, taskComplete: true, taskFailed: true, calendarReminder: true, sound: false, desktopBanner: true })
    const notifItems = [
        { key: 'taskComplete', icon: 'mdi-check-circle-outline', label: 'Task Completed', desc: 'Notify when a scheduled task finishes successfully' },
        { key: 'taskFailed', icon: 'mdi-alert-circle-outline', label: 'Task Failed', desc: 'Notify when a task encounters an error or failure' },
        { key: 'calendarReminder', icon: 'mdi-calendar-clock-outline', label: 'Calendar Reminders', desc: 'Remind you before upcoming events (15 min default)' },
        { key: 'sound', icon: 'mdi-volume-high', label: 'Notification Sound', desc: 'Play a sound when a notification arrives' },
        { key: 'desktopBanner', icon: 'mdi-message-badge-outline', label: 'Desktop Banner', desc: 'Show OS-level desktop banner notifications' },
    ]
</script>

<style scoped>

    /* 旋转动画（框架无法实现） */
    .spin-icon {
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        from {
            transform: rotate(0deg);
        }

        to {
            transform: rotate(360deg);
        }
    }

    /* 快捷键录制显示框（需要特定样式状态切换，保留） */
    .shortcut-display {
        height: 36px;
        border-radius: 8px;
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        display: flex;
        align-items: center;
        padding: 0 12px;
        font-family: monospace;
        font-size: 14px;
        transition: border-color 0.15s, background 0.15s, color 0.15s;
    }

    .shortcut-display--recording {
        border-color: rgb(var(--v-theme-primary));
        background: rgba(var(--v-theme-primary), 0.05);
        color: rgb(var(--v-theme-primary));
    }

    .recording-text {
        font-family: inherit;
        font-size: 12px;
        animation: pulse-opacity 1.5s ease-in-out infinite;
    }

    @keyframes pulse-opacity {

        0%,
        100% {
            opacity: 1;
        }

        50% {
            opacity: 0.5;
        }
    }
</style>
