/** 支持的文件类别 */
export type FileCategory =
  | 'image'
  | 'pdf'
  | 'markdown'
  | 'ppt'
  | 'pptx'
  | 'doc'
  | 'docx'
  | 'txt'
  | 'other'

/** 附件文件对象 */
export interface AttachmentFile {
  /** 唯一标识（随机 ID） */
  id: string
  /** 原始文件名 */
  name: string
  /** 文件大小（字节） */
  size: number
  /** MIME type */
  type: string
  /** 文件类别 */
  category: FileCategory
  /** base64 data URL（图片用于预览，其他类型也保留原始数据） */
  dataUrl: string
  /** MD5 哈希值，用于重复检测 */
  md5: string
}

export interface UserMessageAttachment {
  id: string
  name?: string
  category: FileCategory
  size?: number
  previewUrl?: string
  dataUrl?: string
  status: 'loading' | 'ready'
  source: 'local' | 'history'
}
