import { ref } from 'vue'
import type { UserMessageAttachment } from '@/types/attachment'

export interface PendingPromptPayload {
  content: string
  attachments: UserMessageAttachment[]
}

export const pendingPrompt = ref<PendingPromptPayload | null>(null)
