// Utilities
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { Conversation } from '@/types/conversation'

const CONTENT_SIDEBAR_OPEN_STORAGE_KEY = 'opencrab:content-sidebar-open'

function readContentSidebarOpen () {
  if (typeof window === 'undefined') return true

  const raw = window.localStorage.getItem(CONTENT_SIDEBAR_OPEN_STORAGE_KEY)
  if (raw === null) return true

  return raw === 'true'
}

export const useAppStore = defineStore('app', () => {
  /** 最近一次 set_title SSE 事件产生的标题更新，供侧边栏消费 */
  const conversationTitleUpdate = ref<{ conversation_id: string; title: string } | null>(null)
  const conversationCreated = ref<Conversation | null>(null)
  const contentSidebarOpen = ref(readContentSidebarOpen())

  watch(contentSidebarOpen, value => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(CONTENT_SIDEBAR_OPEN_STORAGE_KEY, String(value))
  })

  function setConversationTitle (conversation_id: string, title: string) {
    conversationTitleUpdate.value = { conversation_id, title }
  }

  function setConversationCreated (conversation: Conversation) {
    conversationCreated.value = { ...conversation }
  }

  function toggleContentSidebar () {
    contentSidebarOpen.value = !contentSidebarOpen.value
  }

  return {
    conversationTitleUpdate,
    conversationCreated,
    contentSidebarOpen,
    setConversationTitle,
    setConversationCreated,
    toggleContentSidebar,
  }
})
