export interface StoreTag {
  id: number
  name: string
}

export interface StoreSkillSummary {
  id: number
  name: string
  description: string
  install: boolean
  download_count: number
  tags: StoreTag[]
  created_at: string
}

export interface StoreSkillDetail extends StoreSkillSummary {
  markdown_content: string
}

export interface StoreMySkill extends StoreSkillSummary {
  status: 'pending' | 'approved' | 'rejected' | 'archived'
  rejection_reason: string | null
  markdown_content: string
}

export interface StoreDownloadedSkill extends StoreSkillSummary {
  install: true
}

export interface LocalDownloadedSkill {
  cloud_skill_id: number
  name: string
  description: string
  markdown_path: string
}

export interface LocalDownloadedSkillDetail extends LocalDownloadedSkill {
  markdown_content: string
}

export interface StoreSkillListResponse {
  total: number
  page: number
  page_size: number
  skills: StoreSkillSummary[]
}

export interface AdminPendingSkill {
  id: number
  name: string
  description: string
  markdown_content: string
  status: 'pending'
  user_email: string
  tags: StoreTag[]
  created_at: string
}

export interface AdminDashboardResponse {
  pending_count: number
  approved_count: number
  week_new: number
  total_downloads: number
}

export interface AdminSkillActionResponse {
  message: string
  skill_id: number
}
