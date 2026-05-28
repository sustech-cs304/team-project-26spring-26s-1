/**
 * router/index.ts
 *
 * Automatic routes for ./src/pages/*.vue
 */

import { setupLayouts } from 'virtual:generated-layouts'
// Composables
import { createRouter, createWebHistory } from 'vue-router'
import { routes } from 'vue-router/auto-routes'
import { isOnboardingCompleted } from '@/composables/useOnboardingConfig'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: setupLayouts(routes),
})

router.beforeEach(async (to) => {
  if (to.path === '/') {
    return {
      path: '/c/',
      query: to.query,
      hash: to.hash,
      replace: true,
    }
  }

  const publicPrefixes = ['/onboarding', '/auth']
  const isPublicRoute = publicPrefixes.some(prefix => to.path.startsWith(prefix))
  if (isPublicRoute) return true

  if (!isOnboardingCompleted()) {
    return {
      path: '/onboarding',
      query: to.fullPath !== '/onboarding' ? { redirect: to.fullPath } : undefined,
    }
  }

  return true
})

export default router
