/**
 * plugins/vuetify.ts
 *
 * Framework documentation: https://vuetifyjs.com`
 */

// Composables
import { createVuetify } from 'vuetify'
import { getStoredThemePreference } from '@/utils/theme'
// Styles
import '@mdi/font/css/materialdesignicons.css'

import 'vuetify/styles'

const lightSurface = '#EEEEEE'

// https://vuetifyjs.com/en/introduction/why-vuetify/#feature-guides
export default createVuetify({
  theme: {
    defaultTheme: getStoredThemePreference(),
    themes: {
      light: {
        colors: {
          surface: lightSurface,
        },
      },
    },
  },
})
