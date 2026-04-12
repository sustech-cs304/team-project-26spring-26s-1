/**
 * main.ts
 *
 * Bootstraps Vuetify and other plugins then mounts the App`
 */

// Composables
import { createApp } from 'vue'

// Plugins
import { registerPlugins } from '@/plugins'
import { installDeepLinkHandler } from '@/utils/deeplink'
import { installGlobalLinkHandler } from '@/utils/link'

// Components
import App from './App.vue'

// Styles
import 'unfonts.css'
import 'katex/dist/katex.min.css'

const app = createApp(App)

registerPlugins(app)
installGlobalLinkHandler()
void installDeepLinkHandler()

app.mount('#app')

let timerMap = new WeakMap<Element, ReturnType<typeof setTimeout>>()

// window.addEventListener(
//     'scroll',
//     (e) => {
//         const target = e.target

//         // 过滤 window / document
//         if (!target || !(target instanceof Element) || target === document.documentElement) {
//             return
//         }

//         target.classList.add('scrolling')

//         const oldTimer = timerMap.get(target)
//         if (oldTimer) clearTimeout(oldTimer)

//         const timer = setTimeout(() => {
//             target.classList.remove('scrolling')
//         }, 800)

//         timerMap.set(target, timer)
//     },
//     true
// )
