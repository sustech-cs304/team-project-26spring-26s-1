const MAX_SKILL_FILE_SIZE = 1024 * 1024
const BANNED_CODE_BLOCK_REGEX = /```(?:bash|python|sh|powershell|cmd)\b/i

export interface SkillUploadValidationResult {
    name: string
    markdown: string
}

function getSectionValue(markdown: string, sectionName: 'Name' | 'Description' | 'Usage') {
    const headingRegex = new RegExp(`^##\\s+${sectionName}(?:\\s+(.*))?$`, 'im')
    const headingMatch = headingRegex.exec(markdown)

    if (!headingMatch) return null

    const inlineValue = headingMatch[1]?.trim()
    if (inlineValue) return inlineValue

    const contentStart = headingMatch.index + headingMatch[0].length
    const rest = markdown.slice(contentStart)
    const nextHeadingMatch = /^##\s+/m.exec(rest)
    const sectionBody = (nextHeadingMatch ? rest.slice(0, nextHeadingMatch.index) : rest).trim()

    return sectionBody || null
}

export async function validateSkillMarkdownFile(file: File): Promise<SkillUploadValidationResult> {
    const fileName = file.name.toLowerCase()
    const isMarkdown = fileName.endsWith('.md') || file.type === 'text/markdown'
    if (!isMarkdown) {
        throw new Error('仅支持上传 .md 文件')
    }

    if (file.size > MAX_SKILL_FILE_SIZE) {
        throw new Error('文件大小不能超过 1MB')
    }

    const markdown = await file.text()
    const name = getSectionValue(markdown, 'Name')
    const description = getSectionValue(markdown, 'Description')
    const usage = getSectionValue(markdown, 'Usage')

    if (!name || !description || !usage) {
        throw new Error('Markdown 必须包含非空的 ## Name、## Description、## Usage 二级标题内容')
    }

    if (name.length > 50) {
        throw new Error('技能名称不能超过 50 个字符')
    }

    if (BANNED_CODE_BLOCK_REGEX.test(markdown)) {
        throw new Error('Markdown 中不能包含 bash、python、sh、powershell、cmd 代码块')
    }

    return {
        name,
        markdown,
    }
}
