import SparkMD5 from 'spark-md5'
import type { FileCategory } from '@/types/attachment'

// ────────────────────────────────────────────
// 常量
// ────────────────────────────────────────────

/** 最大文件大小：5 MB */
export const MAX_FILE_SIZE = 5 * 1024 * 1024

/** 允许的 MIME 类型 → 文件类别映射 */
const MIME_CATEGORY_MAP: Record<string, FileCategory> = {
  'image/jpeg': 'image',
  'image/png': 'image',
  'image/gif': 'image',
  'image/webp': 'image',
  'image/bmp': 'image',
  'image/svg+xml': 'image',
  'application/pdf': 'pdf',
  'application/vnd.ms-powerpoint': 'ppt',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'ppt',
  'text/markdown': 'markdown',
  'text/plain': 'text',
}

/** 扩展名 → 文件类别映射（作为 MIME 类型的后备） */
const EXT_CATEGORY_MAP: Record<string, FileCategory> = {
  '.jpg': 'image',
  '.jpeg': 'image',
  '.png': 'image',
  '.gif': 'image',
  '.webp': 'image',
  '.bmp': 'image',
  '.svg': 'image',
  '.pdf': 'pdf',
  '.ppt': 'ppt',
  '.pptx': 'ppt',
  '.md': 'markdown',
  '.markdown': 'markdown',
  '.txt': 'text',
}

/** 用于 <input accept> 属性的字符串 */
export const ACCEPT_STRING = [
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
  'image/bmp',
  'image/svg+xml',
  'application/pdf',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'text/markdown',
  'text/plain',
  '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg',
  '.pdf',
  '.ppt', '.pptx',
  '.md', '.markdown',
  '.txt',
].join(',')

// ────────────────────────────────────────────
// 图标 & 颜色映射
// ────────────────────────────────────────────

export interface FileIconInfo {
  icon: string
  color: string
}

const FILE_ICONS: Record<FileCategory, FileIconInfo> = {
  image: { icon: 'mdi-file-image-outline', color: 'green' },
  pdf: { icon: 'mdi-file-pdf-box', color: 'red' },
  ppt: { icon: 'mdi-file-powerpoint-box', color: 'orange-darken-1' },
  markdown: { icon: 'mdi-language-markdown', color: 'blue' },
  text: { icon: 'mdi-file-document-outline', color: 'grey' },
}

/** 获取文件类别对应的图标和颜色 */
export function getFileIcon(category: FileCategory): FileIconInfo {
  return FILE_ICONS[category]
}

// ────────────────────────────────────────────
// 工具函数
// ────────────────────────────────────────────

/** 获取文件扩展名（小写，含 `.`） */
function getExtension(fileName: string): string {
  const idx = fileName.lastIndexOf('.')
  return idx >= 0 ? fileName.slice(idx).toLowerCase() : ''
}

/**
 * 判断文件的类别。
 * 优先根据 MIME type，MIME 匹配不到则根据扩展名兜底。
 */
export function getFileCategory(file: File): FileCategory | null {
  // 优先 MIME
  if (file.type && MIME_CATEGORY_MAP[file.type] != null) {
    return MIME_CATEGORY_MAP[file.type]!
  }
  // 兜底扩展名
  const ext = getExtension(file.name)
  if (ext && EXT_CATEGORY_MAP[ext] != null) {
    return EXT_CATEGORY_MAP[ext]!
  }
  return null
}

/** 校验结果 */
export interface FileValidation {
  valid: boolean
  error?: string
}

/**
 * 校验文件是否可以上传：
 *  1. 类型是否在白名单
 *  2. 大小是否 ≤ 5 MB
 */
export function validateFile(file: File): FileValidation {
  const category = getFileCategory(file)
  if (!category) {
    return {
      valid: false,
      error: `不支持的文件类型：${file.name}`,
    }
  }
  if (file.size > MAX_FILE_SIZE) {
    return {
      valid: false,
      error: `文件 "${file.name}" 大小（${formatFileSize(file.size)}）超过 5 MB 限制`,
    }
  }
  return { valid: true }
}

/**
 * 使用 SparkMD5 增量计算文件的 MD5 哈希值。
 * 将文件分块（2 MB/块）读取，避免大文件一次性加载到内存。
 */
export function computeFileMd5(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunkSize = 2 * 1024 * 1024 // 2 MB
    const spark = new SparkMD5.ArrayBuffer()
    const reader = new FileReader()
    const chunks = Math.ceil(file.size / chunkSize)
    let currentChunk = 0

    reader.onload = (e) => {
      if (e.target?.result instanceof ArrayBuffer) {
        spark.append(e.target.result)
      }
      currentChunk++
      if (currentChunk < chunks) {
        loadNext()
      } else {
        resolve(spark.end())
      }
    }

    reader.onerror = () => {
      reject(new Error(`无法读取文件: ${file.name}`))
    }

    function loadNext() {
      const start = currentChunk * chunkSize
      const end = Math.min(start + chunkSize, file.size)
      reader.readAsArrayBuffer(file.slice(start, end))
    }

    loadNext()
  })
}

/**
 * 格式化文件大小为人类可读字符串。
 * 例如：1536 → "1.5 KB"，2097152 → "2.0 MB"
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const size = bytes / Math.pow(1024, i)
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

/** 生成简单的随机 ID */
export function generateFileId(): string {
  return `file_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}
