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
                <div class="pa-3 d-flex flex-column ga-1">
                    <div v-for="tab in tabs" :key="tab.id" class="settings-tab"
                        :class="{ 'settings-tab--active': activeTab === tab.id }" @click="activeTab = tab.id">
                        <v-icon :size="16" class="flex-shrink-0">{{ tab.icon }}</v-icon>
                        <span class="text-body-2 font-weight-medium flex-grow-1">{{ tab.label }}</span>
                        <v-icon v-if="activeTab === tab.id" size="14">mdi-chevron-right</v-icon>
                    </div>
                </div>
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
                            <div class="d-flex ga-2">
                                <button v-for="p in apiProviders" :key="p" class="provider-btn"
                                    :class="{ 'provider-btn--active': llm.provider === p }" @click="llm.provider = p">
                                    {{ p }}
                                </button>
                            </div>
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
                        <div class="security-tip mb-5">
                            <v-icon size="16" color="success"
                                style="margin-top:2px;flex-shrink:0;">mdi-shield-check</v-icon>
                            <span class="text-caption text-success" style="line-height:1.625;">
                                All credentials are encrypted locally using AES-256 and never transmitted to external
                                servers.
                            </span>
                        </div>

                        <!-- 认证方式 -->
                        <div class="mb-5">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-2">Authentication Method
                            </div>
                            <div class="d-flex ga-2">
                                <button v-for="m in authMethods" :key="m.value" class="provider-btn"
                                    :class="{ 'provider-btn--active': creds.method === m.value }"
                                    @click="creds.method = m.value">
                                    {{ m.label }}
                                </button>
                            </div>
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
                        <div class="startup-card mb-5">
                            <div class="d-flex align-center ga-3">
                                <v-icon size="16" class="text-medium-emphasis">mdi-power</v-icon>
                                <div class="flex-grow-1">
                                    <div class="text-body-2 font-weight-medium">Launch on Startup</div>
                                    <div class="text-medium-emphasis" style="font-size:11px;">
                                        Automatically start Agent when system boots
                                    </div>
                                </div>
                                <!-- 自定义开关 -->
                                <div class="custom-switch" :class="{ 'custom-switch--on': prefs.startup }"
                                    @click="prefs.startup = !prefs.startup">
                                    <div class="custom-switch__thumb" />
                                </div>
                            </div>
                        </div>

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
                            <div v-for="cap in capabilities" :key="cap.id" class="cap-row"
                                :class="{ 'cap-row--enabled': cap.enabled }">
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
                                            <span class="text-body-2 font-weight-medium">{{ cap.name }}</span>
                                            <code class="text-medium-emphasis"
                                                style="font-size:10px;">{{ cap.filename }}</code>
                                        </div>
                                        <div class="text-medium-emphasis mt-1" style="font-size:11px;">{{
                                            cap.description }}</div>
                                    </div>
                                    <!-- 开关 -->
                                    <div class="custom-switch" :class="{ 'custom-switch--on': cap.enabled }"
                                        @click="cap.enabled = !cap.enabled">
                                        <div class="custom-switch__thumb" />
                                    </div>
                                </div>
                                <!-- 展开态 -->
                                <div v-if="cap.expanded" class="cap-expand">
                                    <div class="d-flex align-center ga-1 mb-2">
                                        <v-icon size="14" class="text-medium-emphasis">mdi-information-outline</v-icon>
                                        <span class="text-caption font-weight-bold text-medium-emphasis">Required
                                            Permissions</span>
                                    </div>
                                    <ul class="cap-perms">
                                        <li v-for="perm in cap.permissions" :key="perm"
                                            class="d-flex align-center ga-2">
                                            <span class="perm-dot" :class="{ 'perm-dot--enabled': cap.enabled }" />
                                            <span style="font-size:11px;" class="text-medium-emphasis">{{ perm }}</span>
                                        </li>
                                    </ul>
                                </div>
                            </div>
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
</script>

<style scoped>

    /* 左侧导航标签 */
    .settings-tab {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 12px;
        border-radius: 8px;
        cursor: pointer;
        transition: background 0.15s, color 0.15s;
        color: rgba(var(--v-theme-on-surface), 0.6);
    }

    .settings-tab:hover {
        background: rgba(var(--v-theme-surface-variant), 0.5);
        color: rgba(var(--v-theme-on-surface), 1);
    }

    .settings-tab--active {
        background: rgba(var(--v-theme-primary), 0.1);
        color: rgb(var(--v-theme-primary));
    }

    /* Provider / method 按钮 */
    .provider-btn {
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        border-radius: 8px;
        padding: 8px 16px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: border-color 0.15s, background 0.15s, color 0.15s;
        background: transparent;
        color: rgba(var(--v-theme-on-surface), 0.6);
    }

    .provider-btn:hover {
        border-color: rgba(var(--v-theme-on-surface), 0.4);
        color: rgba(var(--v-theme-on-surface), 1);
    }

    .provider-btn--active {
        border-color: rgb(var(--v-theme-primary));
        background: rgba(var(--v-theme-primary), 0.1);
        color: rgb(var(--v-theme-primary));
    }

    /* 旋转动画 */
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

    /* 安全提示 */
    .security-tip {
        border: 1px solid rgba(var(--v-theme-success), 0.2);
        background: rgba(var(--v-theme-success), 0.05);
        border-radius: 8px;
        padding: 12px;
        display: flex;
        align-items: flex-start;
        gap: 12px;
    }

    /* 快捷键显示 */
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

    /* 开机自启动卡片 */
    .startup-card {
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        border-radius: 8px;
        padding: 12px 16px;
    }

    /* 自定义开关 */
    .custom-switch {
        width: 36px;
        height: 20px;
        border-radius: 9999px;
        background: rgba(var(--v-theme-on-surface), 0.2);
        position: relative;
        cursor: pointer;
        transition: background 0.2s;
        flex-shrink: 0;
    }

    .custom-switch--on {
        background: rgb(var(--v-theme-primary));
    }

    .custom-switch__thumb {
        position: absolute;
        top: 2px;
        left: 2px;
        width: 16px;
        height: 16px;
        border-radius: 50%;
        background: #fff;
        transition: transform 0.2s;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
    }

    .custom-switch--on .custom-switch__thumb {
        transform: translateX(16px);
    }

    /* Capability 行 */
    .cap-row {
        border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
        border-radius: 8px;
        overflow: hidden;
        transition: border-color 0.15s, background 0.15s;
    }

    .cap-row--enabled {
        border-color: rgba(var(--v-theme-primary), 0.2);
        background: rgba(var(--v-theme-primary), 0.03);
    }

    .cap-expand {
        border-top: 1px solid rgba(var(--v-border-color), 0.5);
        padding: 12px 16px;
    }

    .cap-perms {
        list-style: none;
        padding: 0;
        margin: 0;
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding-left: 20px;
    }

    .perm-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: rgba(var(--v-theme-on-surface), 0.3);
        flex-shrink: 0;
    }

    .perm-dot--enabled {
        background: rgb(var(--v-theme-primary));
    }
</style>
