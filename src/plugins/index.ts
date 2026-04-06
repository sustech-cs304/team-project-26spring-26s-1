import { install as VueMonacoEditorPlugin } from '@guolao/vue-monaco-editor'
import { createPinia } from 'pinia'

import type { App } from 'vue'

import router from '../router'
import i18n from './i18n'
import vuetify from './vuetify'

/**
 * plugins/index.ts
 *
 * Automatically included in `./src/main.ts`
 */

export function registerPlugins(app: App) {
    app.use(vuetify)
    app.use(createPinia())
    app.use(i18n)
    app.use(router)
    app.use(VueMonacoEditorPlugin)
}
