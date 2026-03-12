// Utilities
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  /** 最近一次 set_title SSE 事件产生的标题更新，供侧边栏消费 */
  const conversationTitleUpdate = ref<{ conversation_id: string; title: string } | null>(null)

  function setConversationTitle (conversation_id: string, title: string) {
    conversationTitleUpdate.value = { conversation_id, title }
  }

  return { conversationTitleUpdate, setConversationTitle }
})
