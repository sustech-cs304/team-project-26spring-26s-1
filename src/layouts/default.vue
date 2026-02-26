<template>
    <v-layout class="rounded rounded-md border">
        <v-app-bar ref="appBarRef" height="32">
            <v-app-bar-title>My app</v-app-bar-title>
            <template #append>
                <div ref="btnGroupRef">
                    <v-btn size="small" @click="minimize" text :ripple="false">
                        <v-icon>mdi-minus</v-icon>
                    </v-btn>
                    <v-btn size="small" @click="toggleMaximize" text :ripple="false">
                        <v-icon v-if="isMaximized">mdi-fullscreen-exit</v-icon>
                        <v-icon v-else>mdi-fullscreen</v-icon>
                    </v-btn>
                    <v-btn size="small" @click="closeWindow" plain :ripple="false" color="error">
                        <v-icon>mdi-close</v-icon>
                    </v-btn>
                </div>
            </template>
        </v-app-bar>

        <v-navigation-drawer permanent rail rail-width="42">
            <v-list nav class="px-0 flex-grow-1">
                <v-menu location="end">
                    <template #activator="{ props }">
                        <div class="d-flex justify-center my-2" v-bind="props">
                            <v-avatar size="32" color="secondary" variant="outlined">
                                <v-icon>mdi-account</v-icon>
                            </v-avatar>
                        </div>
                    </template>
                    <v-card rounded="lg" min-width="200">
                        <v-card-text>
                            <div class="text-subtitle-2 font-weight-semibold">John Doe</div>
                            <div class="text-caption text-medium-emphasis">john@example.com</div>
                        </v-card-text>
                        <v-divider />
                        <v-list-item prepend-icon="mdi-logout" title="退出登录" @click="logout" />
                    </v-card>
                </v-menu>
                <v-divider class="pb-2"></v-divider>
                <nav-icon-item title="Home" icon="mdi-home" to="/" />
                <nav-icon-item title="Chat" icon="mdi-message" to="/chat" />
                <nav-icon-item title="Calendar" icon="mdi-calendar" to="/calendar" />
                <nav-icon-item title="Store" icon="mdi-connection" to="/store" />
                <nav-icon-item title="Settings" icon="mdi-cog" to="/settings" />
            </v-list>
            <template #append>
                <div class="d-flex justify-center py-3">
                    <TokenUsageIndicator :used-tokens="120" :total-tokens="500" />
                </div>
            </template>
        </v-navigation-drawer>

        <!-- <v-navigation-drawer location="right">
            <v-list nav>
                <v-list-item title="Drawer right" link></v-list-item>
            </v-list>
        </v-navigation-drawer> -->

        <v-main>
            <router-view />
        </v-main>
    </v-layout>
</template>
<script setup lang="ts">
    import { getCurrentWindow } from '@tauri-apps/api/window'
    import NavIconItem from '@/components/NavIconItem.vue'
    import TokenUsageIndicator from '@/components/TokenUsageIndicator.vue'

    const appWindow = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
        ? getCurrentWindow()
        : null

    const appBarRef = useTemplateRef<{ $el: HTMLElement }>('appBarRef')
    const btnGroupRef = useTemplateRef<HTMLElement>('btnGroupRef')

    watchEffect((onCleanup) => {
        const el = appBarRef.value?.$el
        if (!el || !appWindow) return

        const onMousedown = (e: MouseEvent) => {
            if (e.button === 0 && !btnGroupRef.value?.contains(e.target as Node)) {
                void appWindow.startDragging()
            }
        }

        el.addEventListener('mousedown', onMousedown)
        onCleanup(() => el.removeEventListener('mousedown', onMousedown))
    })

    const minimize = () => void appWindow?.minimize()

    const isMaximized = ref(false)
    const toggleMaximize = async () => {
        if (!appWindow) return
        if (await appWindow.isMaximized()) {
            appWindow.unmaximize()
            isMaximized.value = false
        } else {
            appWindow.maximize()
            isMaximized.value = true
        }
    }

    const logout = () => { }

    const closeWindow = () => void appWindow?.close()
</script>