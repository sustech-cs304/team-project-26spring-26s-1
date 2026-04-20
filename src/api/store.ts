import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import http, { baseURL } from '@/utils/http'
import type {
  AdminDashboardResponse,
  AdminPendingSkill,
  AdminSkillActionResponse,
  LocalDownloadedSkill,
  LocalDownloadedSkillDetail,
  StoreMySkill,
  StoreSkillDetail,
  StoreSkillListResponse,
  StoreTag,
} from '@/types/store'

export interface GetSkillsParams {
  page?: number
  page_size?: number
  tag_id?: number
  search?: string
}

export interface UploadSkillResponse {
  message: string
  skill_id: number
  status?: 'pending' | 'approved' | 'rejected' | 'archived' | string
}

export interface DeleteSkillResponse {
  message: string
}

export interface StoreSkillActionResponse {
  message: string
  skill_id: number
}

const STORE_API_BASE_URL = (import.meta.env.VITE_STORE_API_BASE_URL as string | undefined) ?? ''

const storeHttp: AxiosInstance | null = STORE_API_BASE_URL
  ? axios.create({
    baseURL: STORE_API_BASE_URL,
    timeout: 10000,
    withCredentials: true,
    headers: {
      'Content-Type': 'application/json',
    },
  })
  : null

if (storeHttp) {
  storeHttp.interceptors.response.use((response: AxiosResponse) => response.data)
}

const storeRequest = {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return storeHttp ? storeHttp.get(url, config) as Promise<T> : http.get<T>(url, config)
  },
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return storeHttp ? storeHttp.post(url, data, config) as Promise<T> : http.post<T>(url, data, config)
  },
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return storeHttp ? storeHttp.delete(url, config) as Promise<T> : http.delete<T>(url, config)
  },
}

function getStoreBaseURL() {
  if (STORE_API_BASE_URL) {
    return STORE_API_BASE_URL
  }

  return /\/api$/i.test(baseURL)
    ? baseURL
    : `${baseURL.replace(/\/+$/, '')}/api`
}

function buildApiUrl(path: string) {
  const storeBaseURL = getStoreBaseURL()
  const normalizedBase = /^https?:/i.test(storeBaseURL)
    ? `${storeBaseURL.replace(/\/+$/, '')}/`
    : new URL(`${storeBaseURL.replace(/^\/+/, '').replace(/\/+$/, '')}/`, `${window.location.origin}/`).toString()

  return new URL(path.replace(/^\/+/, ''), normalizedBase).toString()
}

function normalizeSkillActionResponse(
  payload: Partial<StoreSkillActionResponse> & { detail?: string } | undefined,
  fallbackMessage: string,
  fallbackSkillId: number,
): StoreSkillActionResponse {
  return {
    message: payload?.message || payload?.detail || fallbackMessage,
    skill_id: payload?.skill_id ?? fallbackSkillId,
  }
}

export function getSkills(params: GetSkillsParams = {}): Promise<StoreSkillListResponse> {
  return storeRequest.get<StoreSkillListResponse>('/skills', { params })
}

export function getSkillDetail(skillId: number): Promise<StoreSkillDetail> {
  return storeRequest.get<StoreSkillDetail>(`/skills/${skillId}`)
}

export function getTags(): Promise<StoreTag[]> {
  return storeRequest.get<StoreTag[]>('/tags')
}

export function getMySkills(): Promise<StoreMySkill[]>
export function getMySkills(): Promise<StoreMySkill[]> {
  return storeRequest.get<StoreMySkill[]>('/skills/me')
}

export function getDownloadedSkills(): Promise<LocalDownloadedSkill[]> {
  return storeRequest.get<LocalDownloadedSkill[]>('/skills/downloaded')
}

export function getDownloadedSkillDetail(skillId: number): Promise<LocalDownloadedSkillDetail> {
  return storeRequest.get<LocalDownloadedSkillDetail>(`/skills/downloaded/${skillId}`)
}

export async function uploadSkill(file: File, tagIds: number[] = []): Promise<UploadSkillResponse> {
  const formData = new FormData()
  formData.append('file', file)
  if (tagIds.length > 0) {
    formData.append('tag_ids', tagIds.join(','))
  }

  return storeRequest.post<UploadSkillResponse>('/skills', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

export function deleteMySkill(skillId: number): Promise<DeleteSkillResponse> {
  return storeRequest.delete<DeleteSkillResponse>(`/skill/${skillId}/delete`)
}

export async function triggerSkillDownload(skillId: number): Promise<StoreSkillActionResponse> {
  const response = await storeRequest.get<Partial<StoreSkillActionResponse> & { detail?: string }>(
    `/skills/${skillId}/download`,
  )

  return normalizeSkillActionResponse(response, '下载成功', skillId)
}

export async function triggerSkillUninstall(skillId: number): Promise<StoreSkillActionResponse> {
  const response = await storeRequest.post<Partial<StoreSkillActionResponse> & { detail?: string }>(
    `/skill/${skillId}/uninstall`,
  )

  return normalizeSkillActionResponse(response, '卸载成功', skillId)
}

export function getAdminPendingPageUrl() {
  return new URL('../admin/pending', buildApiUrl('')).toString()
}

export function getAdminDashboard(): Promise<AdminDashboardResponse> {
  return storeRequest.get<AdminDashboardResponse>('/admin/dashboard')
}

export function getAdminPendingSkills(sort: 'asc' | 'desc' = 'desc'): Promise<AdminPendingSkill[]> {
  return storeRequest.get<AdminPendingSkill[]>('/admin/skills/pending', {
    params: { sort },
  })
}

export function approveAdminSkill(skillId: number): Promise<AdminSkillActionResponse> {
  return storeRequest.post<AdminSkillActionResponse>(`/admin/skills/${skillId}/approve`)
}

export function rejectAdminSkill(skillId: number, reason: string): Promise<AdminSkillActionResponse> {
  return storeRequest.post<AdminSkillActionResponse>(`/admin/skills/${skillId}/reject`, {
    reason,
  })
}
