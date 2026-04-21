<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0">
        <div class="d-flex flex-grow-1 overflow-hidden">
            <v-sheet class="flex-shrink-0 overflow-y-auto border-e" color="transparent" width="220">
                <v-list density="compact" class="pa-2" nav>
                    <v-list-item v-for="tab in tabs" :key="tab.id" :prepend-icon="tab.icon" :title="tab.label"
                        :active="activeTab === tab.id" active-color="primary" rounded="lg"
                        @click="activeTab = tab.id" />
                </v-list>
            </v-sheet>

            <v-sheet color="transparent" class="flex-grow-1 overflow-y-auto">
                <v-container max-width="672" class="pa-6">
                    <template v-if="isConfigTab(activeTab)">

                        <div v-if="loadingConfig" class="d-flex justify-center py-16">
                            <v-progress-circular indeterminate color="primary" />
                        </div>

                        <div v-else-if="loadError">
                            <v-alert rounded="lg" variant="tonal" type="error" class="mb-5">
                                {{ loadError }}
                            </v-alert>

                            <v-btn size="small" rounded="lg" variant="flat" color="primary" @click="loadConfigData">
                                Retry Loading Config
                            </v-btn>
                        </div>

                        <div v-else-if="activeTab === 'llm'">
                            <div class="text-subtitle-1 font-weight-bold mb-1">LLM Configuration</div>
                            <div class="text-caption text-medium-emphasis mb-4">
                                Edit the backend `api.agent` endpoint used as the primary model.
                            </div>

                            <div class="d-flex align-center ga-2 flex-wrap mb-5">
                                <v-chip size="small" rounded="lg" variant="tonal" color="primary">
                                    {{ llm.provider }}
                                </v-chip>
                                <div class="text-caption text-medium-emphasis">
                                    Provider type is kept from backend config and is not editable here.
                                </div>
                            </div>

                            <div class="mb-5">
                                <div class="text-caption font-weight-medium text-medium-emphasis mb-2">Base URL</div>
                                <v-text-field v-model="llm.baseUrl" density="compact" variant="solo-filled" flat
                                    rounded="lg" hide-details="auto" />
                                <div class="text-caption text-medium-emphasis mt-1">
                                    Supports reverse proxy or custom relay endpoints.
                                </div>
                            </div>

                            <div class="mb-5">
                                <div class="text-caption font-weight-medium text-medium-emphasis mb-2">API Key</div>
                                <v-text-field v-model="llm.apiKey" density="compact" variant="solo-filled" flat
                                    rounded="lg" hide-details="auto"
                                    :type="visibility.llmApiKey ? 'text' : 'password'"
                                    :append-inner-icon="visibility.llmApiKey ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                    @click:append-inner="visibility.llmApiKey = !visibility.llmApiKey" />
                            </div>

                            <div class="mb-5">
                                <div class="text-caption font-weight-medium text-medium-emphasis mb-2">Model Name</div>
                                <v-text-field v-model="llm.modelName" density="compact" variant="solo-filled" flat
                                    rounded="lg" hide-details="auto" />
                            </div>

                            <v-divider class="mb-4" />
                            <v-btn size="small" rounded="lg" variant="flat" color="primary" :loading="saving.llm"
                                @click="saveLlmConfiguration">
                                Save Configuration
                            </v-btn>
                        </div>

                        <div v-else-if="activeTab === 'file'">
                            <div class="text-subtitle-1 font-weight-bold mb-1">File Configuration</div>
                            <div class="text-caption text-medium-emphasis mb-6">
                                Only the `file.mineru.api_key` value is editable from the frontend.
                            </div>

                            <div class="mb-5">
                                <div class="text-caption font-weight-medium text-medium-emphasis mb-2">MinerU API Key</div>
                                <v-text-field v-model="fileConfig.mineruApiKey" density="compact"
                                    variant="solo-filled" flat rounded="lg" hide-details="auto"
                                    :type="visibility.fileApiKey ? 'text' : 'password'"
                                    :append-inner-icon="visibility.fileApiKey ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                    @click:append-inner="visibility.fileApiKey = !visibility.fileApiKey" />
                            </div>

                            <v-divider class="mb-4" />
                            <v-btn size="small" rounded="lg" variant="flat" color="primary" :loading="saving.file"
                                @click="saveFileConfiguration">
                                Save File Configuration
                            </v-btn>
                        </div>

                        <div v-else-if="activeTab === 'onebot'">
                            <div class="text-subtitle-1 font-weight-bold mb-1">OneBot</div>
                            <div class="text-caption text-medium-emphasis mb-6">
                                Edit the backend-managed OneBot token and superuser list.
                            </div>

                            <div class="mb-5">
                                <div class="text-caption font-weight-medium text-medium-emphasis mb-2">Bot Token</div>
                                <v-text-field v-model="onebot.token" density="compact" variant="solo-filled" flat
                                    rounded="lg" hide-details="auto"
                                    :type="visibility.onebotToken ? 'text' : 'password'"
                                    :append-inner-icon="visibility.onebotToken ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                    @click:append-inner="visibility.onebotToken = !visibility.onebotToken" />
                            </div>

                            <div class="mb-5">
                                <div class="text-caption font-weight-medium text-medium-emphasis mb-2">Superuser IDs</div>
                                <v-textarea v-model="onebot.superuserIdsText" density="compact"
                                    variant="solo-filled" flat rounded="lg" hide-details="auto" rows="4"
                                    auto-grow placeholder="123456&#10;789012" />
                                <div class="text-caption text-medium-emphasis mt-1">
                                    Enter one OneBot superuser ID per line. Commas are also supported.
                                </div>
                            </div>

                            <v-divider class="mb-4" />
                            <v-btn size="small" rounded="lg" variant="flat" color="primary"
                                :loading="saving.onebot" @click="saveOnebotConfiguration">
                                Save OneBot Settings
                            </v-btn>
                        </div>

                        <div v-else-if="activeTab === 'telegram'">
                            <div class="text-subtitle-1 font-weight-bold mb-1">Telegram</div>
                            <div class="text-caption text-medium-emphasis mb-6">
                                Edit the backend-managed Telegram bot token and superuser list.
                            </div>

                            <div class="mb-5">
                                <div class="text-caption font-weight-medium text-medium-emphasis mb-2">Bot Token</div>
                                <v-text-field v-model="telegram.token" density="compact" variant="solo-filled" flat
                                    rounded="lg" hide-details="auto"
                                    :type="visibility.telegramToken ? 'text' : 'password'"
                                    :append-inner-icon="visibility.telegramToken ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                    @click:append-inner="visibility.telegramToken = !visibility.telegramToken" />
                            </div>

                            <div class="mb-5">
                                <div class="text-caption font-weight-medium text-medium-emphasis mb-2">Superuser IDs</div>
                                <v-textarea v-model="telegram.superuserIdsText" density="compact"
                                    variant="solo-filled" flat rounded="lg" hide-details="auto" rows="4"
                                    auto-grow placeholder="123456&#10;789012" />
                                <div class="text-caption text-medium-emphasis mt-1">
                                    Enter one Telegram user ID per line. Commas are also supported.
                                </div>
                            </div>

                            <v-divider class="mb-4" />
                            <v-btn size="small" rounded="lg" variant="flat" color="primary"
                                :loading="saving.telegram" @click="saveTelegramConfiguration">
                                Save Telegram Settings
                            </v-btn>
                        </div>
                    </template>

                    <div v-else-if="activeTab === 'credentials'">
                        <div class="text-subtitle-1 font-weight-bold mb-1">Credential Vault</div>
                        <div class="text-caption text-medium-emphasis mb-4">
                            Securely store and manage your SUSTech authentication credentials.
                        </div>

                        <v-alert rounded="lg" variant="tonal" type="info" class="mb-5">
                            Credentials are kept locally for the current frontend flow and synced to the backend CAS
                            configuration when you save.
                        </v-alert>

                        <div class="mb-4">
                            <div class="text-caption text-medium-emphasis mb-1">Student ID</div>
                            <v-text-field v-model="creds.studentId" density="compact" variant="solo-filled" flat
                                rounded="lg" placeholder="e.g. 12110001" hide-details="auto" />
                        </div>

                        <div class="mb-5">
                            <div class="text-caption text-medium-emphasis mb-1">Password</div>
                            <v-text-field v-model="creds.password" density="compact" variant="solo-filled" flat
                                rounded="lg" hide-details="auto" :type="showPassword ? 'text' : 'password'"
                                :append-inner-icon="showPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                @click:append-inner="showPassword = !showPassword" />
                        </div>

                        <v-divider class="mb-4" />
                        <v-btn size="small" rounded="lg" variant="flat" color="primary"
                            :loading="saving.credentials" @click="saveCredentialVault">
                            Save Credentials
                        </v-btn>
                    </div>

                    <div v-else-if="activeTab === 'appearance'">
                        <div class="text-subtitle-1 font-weight-bold mb-1">Appearance</div>
                        <div class="text-caption text-medium-emphasis mb-6">
                            Customize the look and feel of the application.
                        </div>

                        <div class="mb-5">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-2">Theme</div>
                            <v-item-group v-model="appearance.theme" mandatory>
                                <v-row density="compact">
                                    <v-col v-for="option in themeOptions" :key="option.value" cols="12" sm="4">
                                        <v-item v-slot="{ isSelected, toggle }" :value="option.value">
                                            <v-card rounded="lg" elevation="0"
                                                :variant="isSelected ? 'tonal' : 'outlined'"
                                                :color="isSelected ? 'primary' : undefined" @click="toggle">
                                                <v-card-text class="pa-4">
                                                    <div class="d-flex align-start ga-3">
                                                        <v-avatar rounded="lg" size="32"
                                                            :color="isSelected ? 'primary' : 'surface-variant'"
                                                            :variant="isSelected ? 'flat' : 'tonal'">
                                                            <v-icon size="18">{{ option.icon }}</v-icon>
                                                        </v-avatar>
                                                        <div class="flex-grow-1">
                                                            <div class="d-flex align-center justify-space-between ga-2">
                                                                <div class="text-body-2 font-weight-medium">
                                                                    {{ option.label }}
                                                                </div>
                                                                <v-icon v-if="isSelected" size="16" color="primary">
                                                                    mdi-check-circle
                                                                </v-icon>
                                                            </div>
                                                            <div class="text-caption text-medium-emphasis mt-1">
                                                                {{ option.description }}
                                                            </div>
                                                        </div>
                                                    </div>
                                                </v-card-text>
                                            </v-card>
                                        </v-item>
                                    </v-col>
                                </v-row>
                            </v-item-group>
                            <div class="text-caption text-medium-emphasis mt-1">
                                System mode follows your OS appearance settings.
                            </div>
                        </div>

                        <v-divider class="mb-4" />
                        <v-btn size="small" rounded="lg" variant="flat" color="primary" @click="saveAppearance">
                            Save Appearance
                        </v-btn>
                    </div>

                    <div v-else-if="activeTab === 'notifications'">
                        <div class="text-subtitle-1 font-weight-bold mb-1">Notifications</div>
                        <div class="text-caption text-medium-emphasis mb-6">
                            Control when and how you receive notifications.
                        </div>

                        <v-card rounded="lg" elevation="0" border class="mb-4" max-width="420">
                            <v-list bg-color="transparent" density="comfortable">
                                <v-list-item prepend-icon="mdi-bell-outline" title="Enable Notifications"
                                    subtitle="Master toggle for all notification types.">
                                    <template #append>
                                        <v-switch v-model="notif.enabled" density="compact" hide-details
                                            color="primary" />
                                    </template>
                                </v-list-item>
                            </v-list>
                        </v-card>

                        <v-card rounded="lg" elevation="0" border class="mb-5 overflow-hidden" max-width="420">
                            <v-list bg-color="transparent" density="comfortable">
                                <template v-for="(item, index) in notifItems" :key="item.key">
                                    <v-list-item :prepend-icon="item.icon" :title="item.label"
                                        :subtitle="item.description">
                                        <template #append>
                                            <v-switch v-model="notif[item.key]" density="compact" hide-details
                                                color="primary" :disabled="!notif.enabled" />
                                        </template>
                                    </v-list-item>
                                    <v-divider v-if="index < notifItems.length - 1" />
                                </template>
                            </v-list>
                        </v-card>

                        <v-divider class="mb-4 mt-2" />
                        <v-btn size="small" rounded="lg" variant="flat" color="primary"
                            @click="saveNotificationSettings">
                            Save Notification Settings
                        </v-btn>
                    </div>

                    <div v-else-if="activeTab === 'preferences'">
                        <div class="text-subtitle-1 font-weight-bold mb-1">System Preferences</div>
                        <div class="text-caption text-medium-emphasis mb-6">
                            Configure system-level behavior of the agent.
                        </div>

                        <div class="mb-5">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-2">Wake Shortcut</div>
                            <v-text-field
                                :model-value="prefs.recording ? 'Listening for a shortcut...' : prefs.shortcut"
                                density="compact" variant="solo-filled" flat rounded="lg" hide-details readonly
                                prepend-inner-icon="mdi-keyboard-outline"
                                :color="prefs.recording ? 'primary' : undefined" />
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

                        <v-card variant="outlined" rounded="lg" class="mb-5" max-width="420">
                            <v-list bg-color="transparent" density="comfortable">
                                <v-list-item prepend-icon="mdi-power" title="Launch on Startup"
                                    subtitle="Automatically start Agent when system boots.">
                                    <template #append>
                                        <v-switch v-model="prefs.startup" density="compact" hide-details
                                            color="primary" />
                                    </template>
                                </v-list-item>
                            </v-list>
                        </v-card>

                        <div class="mb-5">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-2">
                                Default Workspace Path
                            </div>
                            <div class="d-flex ga-2">
                                <v-text-field v-model="prefs.workspacePath" density="compact" variant="solo-filled"
                                    flat rounded="lg" hide-details="auto" class="flex-grow-1" />
                                <v-btn variant="text" rounded="lg" size="small" prepend-icon="mdi-folder-outline"
                                    @click="browseWorkspace">
                                    Browse
                                </v-btn>
                            </div>
                            <div class="text-caption text-medium-emphasis mt-1">
                                Agent will organize files, download courseware, and store data in this directory.
                            </div>
                        </div>

                        <v-divider class="mb-4" />
                        <v-btn size="small" rounded="lg" variant="flat" color="primary" @click="savePreferences">
                            Save Preferences
                        </v-btn>
                    </div>
                </v-container>
            </v-sheet>
        </div>

        <v-snackbar v-model="notice.show" :color="notice.color" timeout="2600" location="top">
            {{ notice.text }}
        </v-snackbar>
    </v-container>
</template>

<script setup lang="ts">
    import { patchCas } from '@/api/cas'
    import { getConfig, patchConfig, type AppConfig, type DeepPartial, type LLMEndpointConfig, type LLMProviderType } from '@/api/config'
    import { useOnboardingConfig } from '@/composables/useOnboardingConfig'
    import { useRoute } from 'vue-router'
    import { useTheme } from 'vuetify'

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
    type ThemePreference = 'system' | 'light' | 'dark'
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
        theme: 'system' as ThemePreference,
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

    function isConfigTab(tab: SettingsTabId) {
        return tab === 'llm' || tab === 'file' || tab === 'onebot' || tab === 'telegram'
    }

    function showNotice(text: string, color: NoticeColor = 'success') {
        notice.show = true
        notice.text = text
        notice.color = color
    }

    function getErrorMessage(error: unknown, fallback: string) {
        const responseMessage = (error as any)?.response?.data?.message || (error as any)?.response?.data?.detail
        return responseMessage || (error as any)?.message || fallback
    }

    function applyConfig(config: AppConfig) {
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

    function parseSuperuserIds(value: string) {
        return value
            .split(/[\n,]+/)
            .map(item => item.trim())
            .filter(Boolean)
    }

    function areStringArraysEqual(left: string[], right: string[]) {
        return left.length === right.length && left.every((value, index) => value === right[index])
    }

    async function loadConfigData() {
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

    function buildLlmPatch(): DeepPartial<AppConfig> | null {
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

    function buildFilePatch(): DeepPartial<AppConfig> | null {
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

    function buildOnebotPatch(): DeepPartial<AppConfig> | null {
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

    function buildTelegramPatch() {
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

    async function saveLlmConfiguration() {
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

    async function saveFileConfiguration() {
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

    async function saveOnebotConfiguration() {
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

    async function saveTelegramConfiguration() {
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

    async function saveCredentialVault() {
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

    function saveAppearance() {
        theme.global.name.value = appearance.theme
        showNotice('Appearance saved')
    }

    function saveNotificationSettings() {
        showNotice('Notification settings saved')
    }

    function cleanupShortcutCapture() {
        if (shortcutHandler) {
            window.removeEventListener('keydown', shortcutHandler)
            shortcutHandler = null
        }

        if (recordTimer) {
            clearTimeout(recordTimer)
            recordTimer = null
        }
    }

    function startRecording() {
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

    function browseWorkspace() {
        showNotice('Workspace picker is not connected yet. You can still edit the path manually.', 'warning')
    }

    function savePreferences() {
        showNotice('Preferences saved')
    }

    onMounted(() => {
        void loadConfigData()
    })

    onBeforeUnmount(() => {
        cleanupShortcutCapture()
    })
</script>
