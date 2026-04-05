import http from '@/utils/http'
import type { FileCategory } from '@/types/attachment'

export interface FileInfoResponse {
  file_id: string
  file_type: Exclude<FileCategory, 'other'> | 'other'
  file_name: string
  file_size?: number
  upload_time?: string
  conversation_id: string
  metadata?: {
    dimensions?: {
      width?: number
      height?: number
    }
    page_count?: number
    markdown_length?: number
  }
  download_url?: string
  preview_url?: string
}

export function getFileInfo(fileId: string): Promise<FileInfoResponse> {
  return http.post<FileInfoResponse>(`/files/${fileId}/info`)
}
