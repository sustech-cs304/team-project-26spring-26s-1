import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import axios from 'axios'
import { getCurrentUser, type MeResponse } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const currentUser = ref<MeResponse | null>(null)
  const authChecking = ref(false)

  const isLoggedIn = computed(() => currentUser.value !== null)

  function setCurrentUser(user: MeResponse | null) {
    currentUser.value = user
  }

  function clearCurrentUser() {
    currentUser.value = null
  }

  async function refreshCurrentUser(): Promise<MeResponse | null> {
    authChecking.value = true

    try {
      const user = await getCurrentUser()
      setCurrentUser(user)
      return user
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        clearCurrentUser()
        return null
      }
      throw error
    } finally {
      authChecking.value = false
    }
  }

  async function ensureAuthenticated(): Promise<boolean> {
    if (currentUser.value) {
      return true
    }

    const user = await refreshCurrentUser()
    return user !== null
  }

  return {
    currentUser,
    authChecking,
    isLoggedIn,
    setCurrentUser,
    clearCurrentUser,
    refreshCurrentUser,
    ensureAuthenticated,
  }
})
