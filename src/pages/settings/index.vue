<template>
    <v-layout class="settings-workspace h-100 overflow-hidden min-height-0">
        <v-navigation-drawer permanent width="250" color="surface" floating class="settings-sidebar min-height-0">
            <v-list density="compact" class="pa-2" nav>
                <v-list-item v-for="tab in tabs" :key="tab.id" :prepend-icon="tab.icon" :title="tab.label"
                    :active="activeTab === tab.id" active-class="theme-active-list-item" rounded="lg" slim
                    prepend-gap="8" :ripple="false" @click="activeTab = tab.id" />
            </v-list>
        </v-navigation-drawer>

        <v-app-bar flat height="48" color="background" class="settings-app-bar">
            <template #prepend>
                <v-icon size="18" class="ml-3">{{ activeTabMeta.icon }}</v-icon>
            </template>

            <div class="settings-app-title">
                {{ activeTabMeta.label }}
            </div>
        </v-app-bar>

        <v-main class="settings-main h-100 overflow-hidden min-height-0">
            <div class="settings-route-panel">
                <div class="settings-content-shell">
                    <template v-if="isConfigTab(activeTab)">

                        <div v-if="loadingConfig" class="d-flex justify-center py-16">
                            <v-progress-circular indeterminate />
                        </div>

                        <div v-else-if="loadError">
                            <v-alert rounded="lg" variant="tonal" type="error" class="mb-5">
                                {{ loadError }}
                            </v-alert>

                            <v-btn size="small" rounded="lg" variant="tonal" @click="loadConfigData">
                                Retry Loading Config
                            </v-btn>
                        </div>

                        <div v-else-if="activeTab === 'llm'">
                            <div class="settings-section-title">LLM Configuration</div>
                            <div class="settings-section-description mb-4">
                                Edit the backend `api.agent` endpoint used as the primary model.
                            </div>

                            <div class="d-flex align-center ga-2 flex-wrap mb-5">
                                <v-chip size="small" rounded="lg" variant="tonal">
                                    {{ llm.provider }}
                                </v-chip>
                                <div class="settings-help-text">
                                    Provider type is kept from backend config and is not editable here.
                                </div>
                            </div>

                            <div class="settings-field">
                                <div class="settings-field-label">Base URL</div>
                                <v-text-field v-model="llm.baseUrl" density="compact" variant="solo-filled" flat
                                    rounded="lg" hide-details="auto" />
                                <div class="settings-help-text mt-1">
                                    Supports reverse proxy or custom relay endpoints.
                                </div>
                            </div>

                            <div class="settings-field">
                                <div class="settings-field-label">API Key</div>
                                <v-text-field v-model="llm.apiKey" density="compact" variant="solo-filled" flat
                                    rounded="lg" hide-details="auto" :type="visibility.llmApiKey ? 'text' : 'password'"
                                    :append-inner-icon="visibility.llmApiKey ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                    @click:append-inner="visibility.llmApiKey = !visibility.llmApiKey" />
                            </div>

                            <div class="settings-field">
                                <div class="settings-field-label">Model Name</div>
                                <v-text-field v-model="llm.modelName" density="compact" variant="solo-filled" flat
                                    rounded="lg" hide-details="auto" />
                            </div>

                            <v-divider class="settings-divider" />
                            <v-btn size="small" rounded="lg" variant="tonal" class="settings-save-button" :loading="saving.llm"
                                @click="saveLlmConfiguration">
                                Save Configuration
                            </v-btn>
                        </div>

                        <div v-else-if="activeTab === 'file'">
                            <div class="settings-section-title">File Configuration</div>
                            <div class="settings-section-description mb-6">
                                Only the `file.mineru.api_key` value is editable from the frontend.
                            </div>

                            <div class="settings-field">
                                <div class="settings-field-label">MinerU API Key</div>
                                <v-text-field v-model="fileConfig.mineruApiKey" density="compact" variant="solo-filled"
                                    flat rounded="lg" hide-details="auto"
                                    :type="visibility.fileApiKey ? 'text' : 'password'"
                                    :append-inner-icon="visibility.fileApiKey ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                    @click:append-inner="visibility.fileApiKey = !visibility.fileApiKey" />
                            </div>

                            <v-divider class="settings-divider" />
                            <v-btn size="small" rounded="lg" variant="tonal" class="settings-save-button" :loading="saving.file"
                                @click="saveFileConfiguration">
                                Save File Configuration
                            </v-btn>
                        </div>

                        <div v-else-if="activeTab === 'onebot'">
                            <div class="settings-section-title">OneBot</div>
                            <div class="settings-section-description mb-6">
                                Edit the backend-managed OneBot token and superuser list.
                            </div>

                            <div class="settings-field">
                                <div class="settings-field-label">Bot Token</div>
                                <v-text-field v-model="onebot.token" density="compact" variant="solo-filled" flat
                                    rounded="lg" hide-details="auto"
                                    :type="visibility.onebotToken ? 'text' : 'password'"
                                    :append-inner-icon="visibility.onebotToken ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                    @click:append-inner="visibility.onebotToken = !visibility.onebotToken" />
                            </div>

                            <div class="settings-field">
                                <div class="settings-field-label">Superuser IDs</div>
                                <v-textarea v-model="onebot.superuserIdsText" density="compact" variant="solo-filled"
                                    flat rounded="lg" hide-details="auto" rows="4" auto-grow
                                    placeholder="123456&#10;789012" />
                                <div class="settings-help-text mt-1">
                                    Enter one OneBot superuser ID per line. Commas are also supported.
                                </div>
                            </div>

                            <v-divider class="settings-divider" />
                            <v-btn size="small" rounded="lg" variant="tonal" class="settings-save-button" :loading="saving.onebot"
                                @click="saveOnebotConfiguration">
                                Save OneBot Settings
                            </v-btn>
                        </div>

                        <div v-else-if="activeTab === 'telegram'">
                            <div class="settings-section-title">Telegram</div>
                            <div class="settings-section-description mb-6">
                                Edit the backend-managed Telegram bot token and superuser list.
                            </div>

                            <div class="settings-field">
                                <div class="settings-field-label">Bot Token</div>
                                <v-text-field v-model="telegram.token" density="compact" variant="solo-filled" flat
                                    rounded="lg" hide-details="auto"
                                    :type="visibility.telegramToken ? 'text' : 'password'"
                                    :append-inner-icon="visibility.telegramToken ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                    @click:append-inner="visibility.telegramToken = !visibility.telegramToken" />
                            </div>

                            <div class="settings-field">
                                <div class="settings-field-label">Superuser IDs</div>
                                <v-textarea v-model="telegram.superuserIdsText" density="compact" variant="solo-filled"
                                    flat rounded="lg" hide-details="auto" rows="4" auto-grow
                                    placeholder="123456&#10;789012" />
                                <div class="settings-help-text mt-1">
                                    Enter one Telegram user ID per line. Commas are also supported.
                                </div>
                            </div>

                            <v-divider class="settings-divider" />
                            <v-btn size="small" rounded="lg" variant="tonal" class="settings-save-button" :loading="saving.telegram"
                                @click="saveTelegramConfiguration">
                                Save Telegram Settings
                            </v-btn>
                        </div>
                    </template>

                    <div v-else-if="activeTab === 'credentials'">
                        <div class="settings-section-title">Credential Vault</div>
                        <div class="settings-section-description mb-4">
                            Securely store and manage your SUSTech authentication credentials.
                        </div>

                        <v-alert rounded="lg" variant="tonal" type="info" density="compact" class="mb-5">
                            Credentials are kept locally for the current frontend flow and synced to the backend CAS
                            configuration when you save.
                        </v-alert>

                        <div class="settings-field">
                            <div class="settings-field-label">Student ID</div>
                            <v-text-field v-model="creds.studentId" density="compact" variant="solo-filled" flat
                                rounded="lg" placeholder="e.g. 12110001" hide-details="auto" />
                        </div>

                        <div class="settings-field">
                            <div class="settings-field-label">Password</div>
                            <v-text-field v-model="creds.password" density="compact" variant="solo-filled" flat
                                rounded="lg" hide-details="auto" :type="showPassword ? 'text' : 'password'"
                                :append-inner-icon="showPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                @click:append-inner="showPassword = !showPassword" />
                        </div>

                        <v-divider class="settings-divider" />
                        <v-btn size="small" rounded="lg" variant="tonal" class="settings-save-button" :loading="saving.credentials"
                            @click="saveCredentialVault">
                            Save Credentials
                        </v-btn>
                    </div>

                    <div v-else-if="activeTab === 'appearance'">
                        <div class="settings-section-title">Appearance</div>
                        <div class="settings-section-description mb-6">
                            Customize the look and feel of the application.
                        </div>

                        <div class="settings-field">
                            <div class="settings-field-label">Theme</div>
                            <v-item-group v-model="appearance.theme" mandatory>
                                <v-row density="compact">
                                    <v-col v-for="option in themeOptions" :key="option.value" cols="12" sm="4">
                                        <v-item v-slot="{ isSelected, toggle }" :value="option.value">
                                            <v-card rounded="lg" elevation="0" border class="settings-option-card"
                                                :class="{ 'settings-option-card--active': isSelected }" @click="toggle">
                                                <v-card-text class="pa-3">
                                                    <div class="d-flex align-center ga-2">
                                                        <v-icon size="18">{{ option.icon }}</v-icon>
                                                        <div class="text-body-2 font-weight-medium">
                                                            {{ option.label }}
                                                        </div>
                                                        <v-spacer />
                                                        <v-icon v-if="isSelected" size="15">mdi-check</v-icon>
                                                    </div>
                                                </v-card-text>
                                            </v-card>
                                        </v-item>
                                    </v-col>
                                </v-row>
                            </v-item-group>
                            <div class="settings-help-text mt-1">
                                System mode follows your OS appearance settings.
                            </div>
                        </div>

                        <v-divider class="settings-divider" />
                        <v-btn size="small" rounded="lg" variant="tonal" class="settings-save-button" @click="saveAppearance">
                            Save Appearance
                        </v-btn>
                    </div>

                    <div v-else-if="activeTab === 'notifications'">
                        <div class="settings-section-title">Notifications</div>
                        <div class="settings-section-description mb-6">
                            Control when and how you receive notifications.
                        </div>

                        <v-card rounded="lg" elevation="0" border class="mb-4">
                            <v-list bg-color="transparent" density="comfortable">
                                <v-list-item prepend-icon="mdi-bell-outline" title="Enable Notifications"
                                    subtitle="Master toggle for all notification types.">
                                    <template #append>
                                        <v-switch v-model="notif.enabled" density="compact" hide-details
                                            inset />
                                    </template>
                                </v-list-item>
                            </v-list>
                        </v-card>

                        <v-card rounded="lg" elevation="0" border class="mb-5 overflow-hidden">
                            <v-list bg-color="transparent" density="comfortable">
                                <template v-for="(item, index) in notifItems" :key="item.key">
                                    <v-list-item :prepend-icon="item.icon" :title="item.label"
                                        :subtitle="item.description">
                                        <template #append>
                                            <v-switch v-model="notif[item.key]" density="compact" hide-details
                                                inset :disabled="!notif.enabled" />
                                        </template>
                                    </v-list-item>
                                    <v-divider v-if="index < notifItems.length - 1" />
                                </template>
                            </v-list>
                        </v-card>

                        <v-divider class="settings-divider" />
                        <v-btn size="small" rounded="lg" variant="tonal" class="settings-save-button"
                            @click="saveNotificationSettings">
                            Save Notification Settings
                        </v-btn>
                    </div>

                    <div v-else-if="activeTab === 'preferences'">
                        <div class="settings-section-title">System Preferences</div>
                        <div class="settings-section-description mb-6">
                            Configure system-level behavior of the agent.
                        </div>

                        <div class="settings-field">
                            <div class="settings-field-label">Wake Shortcut</div>
                            <v-text-field
                                :model-value="prefs.recording ? 'Listening for a shortcut...' : prefs.shortcut"
                                density="compact" variant="solo-filled" flat rounded="lg" hide-details readonly
                                prepend-inner-icon="mdi-keyboard-outline"
                                :focused="prefs.recording" />
                            <div class="d-flex align-center ga-2 mt-3">
                                <v-btn variant="tonal" rounded="lg" size="small" :disabled="prefs.recording"
                                    @click="startRecording">
                                    {{ prefs.recording ? 'Recording...' : 'Record' }}
                                </v-btn>
                                <v-chip v-if="prefs.recording" size="small" rounded="lg" variant="tonal"
                                    color="warning">
                                    Press a key combination...
                                </v-chip>
                            </div>
                        </div>

                        <v-card variant="outlined" rounded="lg" class="mb-5">
                            <v-list bg-color="transparent" density="comfortable">
                                <v-list-item prepend-icon="mdi-power" title="Launch on Startup"
                                    subtitle="Automatically start Agent when system boots.">
                                    <template #append>
                                        <v-switch v-model="prefs.startup" density="compact" hide-details
                                            inset />
                                    </template>
                                </v-list-item>
                            </v-list>
                        </v-card>

                        <div class="settings-field">
                            <div class="settings-field-label">Default Workspace Path</div>
                            <div class="d-flex ga-2">
                                <v-text-field v-model="prefs.workspacePath" density="compact" variant="solo-filled" flat
                                    rounded="lg" hide-details="auto" class="flex-grow-1" />
                                <v-btn variant="text" rounded="lg" size="small" prepend-icon="mdi-folder-outline"
                                    @click="browseWorkspace">
                                    Browse
                                </v-btn>
                            </div>
                            <div class="settings-help-text mt-1">
                                Agent will organize files, download courseware, and store data in this directory.
                            </div>
                        </div>

                        <v-divider class="settings-divider" />
                        <v-btn size="small" rounded="lg" variant="tonal" class="settings-save-button" @click="savePreferences">
                            Save Preferences
                        </v-btn>
                    </div>
                </div>
            </div>
        </v-main>

        <v-snackbar v-model="notice.show" :color="notice.color" timeout="2600" location="top">
            {{ notice.text }}
        </v-snackbar>
    </v-layout>
</template>

<script setup lang="ts">
    import { patchCas } from '@/api/cas'
    import { getConfig, patchConfig, type AppConfig, type DeepPartial, type LLMEndpointConfig, type LLMProviderType } from '@/api/config'
    import { useOnboardingConfig } from '@/composables/useOnboardingConfig'
    import { useRoute } from 'vue-router'
    import { useTheme } from 'vuetify'
    import { getStoredThemePreference, setStoredThemePreference, type ThemePreference } from '@/utils/theme'

    type SettingsTabId =
        | 'llm'
        | 'file'
        | 'onebot'
        | 'telegram'
        | 'credentials'
        | 'appearance'
        | 'notifications'
        | 'preferences'

    type NoticeColor = 'success' | 'error' | 'warning'
    type NotificationKey = 'taskComplete' | 'taskFailed' | 'calendarReminder'

    interface NotificationItem {
        key: NotificationKey
        icon: string
        label: string
        description: string
    }

    const route = useRoute()
    const theme = useTheme()
    const activeTab = ref<SettingsTabId>('llm')
    const { campusAuth, saveCampusAuth } = useOnboardingConfig()

    const tabs: { id: SettingsTabId, icon: string, label: string }[] = [
        { id: 'llm', icon: 'mdi-brain', label: 'LLM Configuration' },
        { id: 'file', icon: 'mdi-file-outline', label: 'File' },
        { id: 'onebot', icon: 'mdi-robot-outline', label: 'OneBot' },
        { id: 'telegram', icon: 'mdi-send-outline', label: 'Telegram' },
        { id: 'credentials', icon: 'mdi-shield-check', label: 'Credential Vault' },
        { id: 'appearance', icon: 'mdi-palette-outline', label: 'Appearance' },
        { id: 'notifications', icon: 'mdi-bell-outline', label: 'Notifications' },
        { id: 'preferences', icon: 'mdi-wrench-outline', label: 'System Preferences' },
    ]

    const activeTabMeta = computed(() =>
        tabs.find(tab => tab.id === activeTab.value) ?? tabs[0]!
    )

    watch(
        () => route.query.tab,
        (value) => {
            if (typeof value !== 'string') return
            if (tabs.some(tab => tab.id === value)) {
                activeTab.value = value as SettingsTabId
            }
        },
        { immediate: true }
    )

    const notice = reactive({
        show: false,
        text: '',
        color: 'success' as NoticeColor,
    })

    const loadingConfig = ref(true)
    const loadError = ref('')
    const loadedConfig = shallowRef<AppConfig | null>(null)

    const saving = reactive({
        llm: false,
        file: false,
        onebot: false,
        telegram: false,
        credentials: false,
    })

    const visibility = reactive({
        llmApiKey: false,
        fileApiKey: false,
        onebotToken: false,
        telegramToken: false,
    })

    const llm = reactive({
        provider: 'OpenAI' as LLMProviderType,
        baseUrl: '',
        apiKey: '',
        modelName: '',
    })

    const fileConfig = reactive({
        mineruApiKey: '',
    })

    const onebot = reactive({
        token: '',
        superuserIdsText: '',
    })

    const telegram = reactive({
        token: '',
        superuserIdsText: '',
    })

    const showPassword = ref(false)
    const creds = reactive({
        studentId: campusAuth.studentId,
        password: campusAuth.password,
    })

    const themeOptions = [
        {
            value: 'system' as ThemePreference,
            label: 'System',
            icon: 'mdi-monitor',
            description: 'Follow your operating system setting.',
        },
        {
            value: 'light' as ThemePreference,
            label: 'Light',
            icon: 'mdi-white-balance-sunny',
            description: 'Use a brighter interface for daytime work.',
        },
        {
            value: 'dark' as ThemePreference,
            label: 'Dark',
            icon: 'mdi-weather-night',
            description: 'Use a darker interface for lower-glare viewing.',
        },
    ]

    const appearance = reactive({
        theme: getStoredThemePreference(),
    })

    const notif = reactive({
        enabled: true,
        taskComplete: true,
        taskFailed: true,
        calendarReminder: true,
    })

    const notifItems: NotificationItem[] = [
        {
            key: 'taskComplete',
            icon: 'mdi-check-circle-outline',
            label: 'Task Completed',
            description: 'Notify when a scheduled task finishes successfully.',
        },
        {
            key: 'taskFailed',
            icon: 'mdi-alert-circle-outline',
            label: 'Task Failed',
            description: 'Notify when a task encounters an error or failure.',
        },
        {
            key: 'calendarReminder',
            icon: 'mdi-calendar-clock-outline',
            label: 'Calendar Reminders',
            description: 'Remind you before upcoming events.',
        },
    ]

    const prefs = reactive({
        shortcut: 'Alt + Space',
        recording: false,
        startup: true,
        workspacePath: '~/Documents/OpenCrab',
    })

    let shortcutHandler: ((event: KeyboardEvent) => void) | null = null
    let recordTimer: ReturnType<typeof setTimeout> | null = null

    function isConfigTab (tab: SettingsTabId) {
        return tab === 'llm' || tab === 'file' || tab === 'onebot' || tab === 'telegram'
    }

    function showNotice (text: string, color: NoticeColor = 'success') {
        notice.show = true
        notice.text = text
        notice.color = color
    }

    function getErrorMessage (error: unknown, fallback: string) {
        const responseMessage = (error as any)?.response?.data?.message || (error as any)?.response?.data?.detail
        return responseMessage || (error as any)?.message || fallback
    }

    function applyConfig (config: AppConfig) {
        loadedConfig.value = config

        llm.provider = config.api.agent.type
        llm.baseUrl = config.api.agent.base_url || ''
        llm.apiKey = config.api.agent.api_key || ''
        llm.modelName = config.api.agent.model || ''

        fileConfig.mineruApiKey = config.file?.mineru?.api_key || ''

        onebot.token = config.onebot?.token || ''
        onebot.superuserIdsText = (config.onebot?.superuser_ids || []).map(id => String(id)).join('\n')

        telegram.token = config.telegram?.token || ''
        telegram.superuserIdsText = (config.telegram?.superuser_ids || []).map(id => String(id)).join('\n')
    }

    function parseSuperuserIds (value: string) {
        return value
            .split(/[\n,]+/)
            .map(item => item.trim())
            .filter(Boolean)
    }

    function areStringArraysEqual (left: string[], right: string[]) {
        return left.length === right.length && left.every((value, index) => value === right[index])
    }

    async function loadConfigData () {
        loadingConfig.value = true
        loadError.value = ''

        try {
            const config = await getConfig()
            applyConfig(config)
        } catch (error) {
            loadError.value = getErrorMessage(error, 'Failed to load backend config.')
        } finally {
            loadingConfig.value = false
        }
    }

    function buildLlmPatch (): DeepPartial<AppConfig> | null {
        const snapshot = loadedConfig.value
        if (!snapshot) return null

        const agentPatch: DeepPartial<LLMEndpointConfig> = {}
        const nextBaseUrl = llm.baseUrl.trim()
        const nextApiKey = llm.apiKey.trim()
        const nextModel = llm.modelName.trim()

        if (nextBaseUrl !== snapshot.api.agent.base_url) {
            agentPatch.base_url = nextBaseUrl
        }

        if (nextApiKey !== snapshot.api.agent.api_key) {
            agentPatch.api_key = nextApiKey
        }

        if (nextModel !== snapshot.api.agent.model) {
            agentPatch.model = nextModel
        }

        if (!Object.keys(agentPatch).length) return null

        return {
            api: {
                agent: agentPatch,
            },
        }
    }

    function buildFilePatch (): DeepPartial<AppConfig> | null {
        const snapshot = loadedConfig.value
        if (!snapshot) return null

        const nextApiKey = fileConfig.mineruApiKey.trim()
        if (nextApiKey === snapshot.file.mineru.api_key) return null

        return {
            file: {
                mineru: {
                    api_key: nextApiKey,
                },
            },
        }
    }

    function buildOnebotPatch (): DeepPartial<AppConfig> | null {
        const snapshot = loadedConfig.value
        if (!snapshot) return null

        const onebotPatch: DeepPartial<AppConfig['onebot']> = {}
        const nextToken = onebot.token.trim()
        const nextSuperuserIds = parseSuperuserIds(onebot.superuserIdsText)

        if (nextToken !== snapshot.onebot.token) {
            onebotPatch.token = nextToken
        }

        if (!areStringArraysEqual(nextSuperuserIds, snapshot.onebot.superuser_ids || [])) {
            onebotPatch.superuser_ids = nextSuperuserIds
        }

        if (!Object.keys(onebotPatch).length) return null

        return {
            onebot: onebotPatch,
        }
    }

    function buildTelegramPatch () {
        const snapshot = loadedConfig.value
        if (!snapshot) return null

        const telegramPatch: NonNullable<DeepPartial<AppConfig['telegram']>> = {}
        const nextToken = telegram.token.trim()
        const nextSuperuserIds = parseSuperuserIds(telegram.superuserIdsText)
        const currentTelegram = snapshot.telegram

        if (nextToken !== (currentTelegram?.token || '')) {
            telegramPatch.token = nextToken
        }

        if (!areStringArraysEqual(nextSuperuserIds, currentTelegram?.superuser_ids || [])) {
            telegramPatch.superuser_ids = nextSuperuserIds
        }

        if (!Object.keys(telegramPatch).length) return null

        return {
            value: {
                telegram: telegramPatch,
            } satisfies DeepPartial<AppConfig>,
        }
    }

    async function saveLlmConfiguration () {
        const delta = buildLlmPatch()
        if (!delta) {
            showNotice('No main model changes to save.', 'warning')
            return
        }

        saving.llm = true

        try {
            const config = await patchConfig(delta)
            applyConfig(config)
            showNotice('Main model configuration saved.')
        } catch (error) {
            showNotice(getErrorMessage(error, 'Failed to save main model configuration.'), 'error')
        } finally {
            saving.llm = false
        }
    }

    async function saveFileConfiguration () {
        const delta = buildFilePatch()
        if (!delta) {
            showNotice('No file API key changes to save.', 'warning')
            return
        }

        saving.file = true

        try {
            const config = await patchConfig(delta)
            applyConfig(config)
            showNotice('File configuration saved.')
        } catch (error) {
            showNotice(getErrorMessage(error, 'Failed to save file configuration.'), 'error')
        } finally {
            saving.file = false
        }
    }

    async function saveOnebotConfiguration () {
        const delta = buildOnebotPatch()
        if (!delta) {
            showNotice('No OneBot changes to save.', 'warning')
            return
        }

        saving.onebot = true

        try {
            const config = await patchConfig(delta)
            applyConfig(config)
            showNotice('OneBot configuration saved.')
        } catch (error) {
            showNotice(getErrorMessage(error, 'Failed to save OneBot configuration.'), 'error')
        } finally {
            saving.onebot = false
        }
    }

    async function saveTelegramConfiguration () {
        const result = buildTelegramPatch()
        if (!result) {
            showNotice('No Telegram changes to save.', 'warning')
            return
        }

        saving.telegram = true

        try {
            const config = await patchConfig(result.value)
            applyConfig(config)
            showNotice('Telegram configuration saved.')
        } catch (error) {
            showNotice(getErrorMessage(error, 'Failed to save Telegram configuration.'), 'error')
        } finally {
            saving.telegram = false
        }
    }

    async function saveCredentialVault () {
        saving.credentials = true

        saveCampusAuth({
            enabled: true,
            studentId: creds.studentId.trim(),
            password: creds.password,
        })

        try {
            const response = await patchCas({
                id: creds.studentId.trim(),
                password: creds.password,
            })
            showNotice(response.message || 'Credential vault saved')
        } catch (error) {
            showNotice(getErrorMessage(error, 'Failed to save CAS credentials.'), 'error')
        } finally {
            saving.credentials = false
        }
    }

    function saveAppearance () {
        setStoredThemePreference(appearance.theme)
        theme.global.name.value = appearance.theme
        showNotice('Appearance saved')
    }

    function saveNotificationSettings () {
        showNotice('Notification settings saved')
    }

    function cleanupShortcutCapture () {
        if (shortcutHandler) {
            window.removeEventListener('keydown', shortcutHandler)
            shortcutHandler = null
        }

        if (recordTimer) {
            clearTimeout(recordTimer)
            recordTimer = null
        }
    }

    function startRecording () {
        cleanupShortcutCapture()
        prefs.recording = true

        shortcutHandler = (event: KeyboardEvent) => {
            event.preventDefault()

            const parts: string[] = []
            if (event.ctrlKey) parts.push('Ctrl')
            if (event.altKey) parts.push('Alt')
            if (event.shiftKey) parts.push('Shift')
            if (event.metaKey) parts.push('Meta')
            if (event.key && !['Control', 'Alt', 'Shift', 'Meta'].includes(event.key)) {
                parts.push(event.key.toUpperCase())
            }

            if (parts.length < 2) return

            prefs.shortcut = parts.join(' + ')
            prefs.recording = false
            cleanupShortcutCapture()
        }

        window.addEventListener('keydown', shortcutHandler)
        recordTimer = window.setTimeout(() => {
            prefs.recording = false
            cleanupShortcutCapture()
        }, 5000)
    }

    function browseWorkspace () {
        showNotice('Workspace picker is not connected yet. You can still edit the path manually.', 'warning')
    }

    function savePreferences () {
        showNotice('Preferences saved')
    }

    onMounted(() => {
        void loadConfigData()
    })

    onBeforeUnmount(() => {
        cleanupShortcutCapture()
    })
</script>

<style scoped>
    .settings-workspace {
        --settings-content-radius: 8px;
        background: rgb(var(--v-theme-surface));
    }

    .settings-sidebar {
        background: rgb(var(--v-theme-surface)) !important;
    }

    .settings-app-bar {
        background: rgb(var(--v-theme-background)) !important;
        border-top-left-radius: var(--settings-content-radius) !important;
        overflow: hidden;
    }

    .settings-app-bar :deep(.v-toolbar__content) {
        position: relative;
    }

    .settings-app-title {
        position: absolute;
        left: 50%;
        max-width: min(44vw, 520px);
        overflow: hidden;
        font-size: 0.875rem;
        font-weight: 600;
        line-height: 1.25rem;
        text-overflow: ellipsis;
        transform: translateX(-50%);
        white-space: nowrap;
    }

    .settings-main {
        background: transparent;
    }

    .settings-route-panel {
        height: 100%;
        min-height: 0;
        overflow: hidden;
        background: rgb(var(--v-theme-background));
        border-bottom-left-radius: var(--settings-content-radius);
    }

    .settings-content-shell {
        width: min(720px, 100%);
        height: 100%;
        min-height: 0;
        margin-inline: auto;
        overflow-y: auto;
        padding: 12px 16px 20px;
    }

    .settings-section-title {
        font-size: 0.9375rem;
        font-weight: 700;
        line-height: 1.35rem;
    }

    .settings-section-description,
    .settings-help-text {
        color: rgba(var(--v-theme-on-surface), 0.62);
        font-size: 0.8125rem;
        line-height: 1.35;
    }

    .settings-field {
        margin-bottom: 14px;
    }

    .settings-field-label {
        margin-bottom: 6px;
        color: rgba(var(--v-theme-on-surface), 0.66);
        font-size: 0.8125rem;
        font-weight: 600;
        line-height: 1.1rem;
    }

    .settings-divider {
        margin: 12px 0;
    }

    .settings-save-button {
        display: flex;
        margin-left: auto;
    }

    .settings-option-card {
        background: rgba(var(--v-theme-on-surface), 0.018) !important;
    }

    .settings-option-card--active {
        background: rgba(var(--v-theme-on-surface), 0.08) !important;
        color: rgb(var(--v-theme-on-surface)) !important;
    }

    .settings-workspace :deep(.theme-active-list-item) {
        background: rgba(var(--v-theme-on-surface), 0.08) !important;
        color: rgb(var(--v-theme-on-surface)) !important;
    }

    .settings-workspace :deep(.theme-active-list-item .v-icon),
    .settings-workspace :deep(.v-list-item--active .v-icon) {
        color: rgb(var(--v-theme-on-surface)) !important;
    }

    .settings-workspace :deep(.v-list-item--active > .v-list-item__overlay),
    .settings-workspace :deep(.theme-active-list-item > .v-list-item__overlay) {
        opacity: 0 !important;
    }

    .settings-workspace :deep(.v-list-item-title) {
        font-size: 0.8125rem;
        font-weight: 600;
    }

    .settings-sidebar :deep(.v-list-item__prepend > .v-icon) {
        font-size: 20px;
        height: 20px;
        width: 20px;
    }

    .settings-workspace :deep(.v-field) {
        font-size: 0.875rem;
    }

    .settings-workspace :deep(.v-switch .v-selection-control) {
        min-height: 32px;
    }

    @media (max-width: 760px) {
        .settings-content-shell {
            width: 100%;
        }
    }
</style>
