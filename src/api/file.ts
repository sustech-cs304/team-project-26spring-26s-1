import http, { baseURL } from '@/utils/http'
import type { FileCategory } from '@/types/attachment'

const UPLOAD_TIMEOUT_MS = 60000

export interface UploadFileResponse {
  file_id: string
  mime_type?: string
}

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

export function uploadFile(file: File): Promise<UploadFileResponse> {
  const formData = new FormData()
  formData.append('file', file)

  return http.post<UploadFileResponse>('/files/upload', formData, {
    timeout: UPLOAD_TIMEOUT_MS,
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

export async function getFileBlob(fileId: string): Promise<Blob> {
  const token = localStorage.getItem('accessToken')
  const response = await fetch(`${baseURL}/file/${fileId}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    credentials: 'include',
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }

  return response.blob()
}
