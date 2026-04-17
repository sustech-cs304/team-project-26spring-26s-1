/**
 * router/index.ts
 *
 * Automatic routes for ./src/pages/*.vue
 */

import { setupLayouts } from 'virtual:generated-layouts'
// Composables
import { createRouter, createWebHistory, type RouteLocationNormalized } from 'vue-router'
import { routes } from 'vue-router/auto-routes'
import { isOnboardingCompleted } from '@/composables/useOnboardingConfig'
import { useAuthStore } from '@/stores/auth'
import { buildLoginRoute } from '@/utils/authSession'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: setupLayouts(routes),
})

function isProtectedStoreRoute(to: RouteLocationNormalized): boolean {
  return to.path === '/store'
}

router.beforeEach(async (to) => {
  if (isProtectedStoreRoute(to)) {
    const authStore = useAuthStore()
    try {
      const authenticated = await authStore.ensureAuthenticated()
      if (!authenticated) {
        return buildLoginRoute(to.fullPath)
      }
    } catch (error) {
      console.error('Auth check failed before navigation:', error)
      return true
    }
  }

  if (import.meta.env.DEV) return true

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
