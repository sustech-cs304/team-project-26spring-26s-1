<template>
    <div ref="rootEl" class="md-body" v-html="rendered" @click="handleCopy" />
</template>

<script lang="ts">
// 模块级：所有 MarkdownRenderer 实例共享同一个引用计数
let _themeRefCount = 0
</script>

<script setup lang="ts">
    import MarkdownIt from 'markdown-it'
    import markdownItKatex from '@vscode/markdown-it-katex'
    import DOMPurify from 'dompurify'
    import hljs from 'highlight.js'
    import { copyText } from '@/utils/copyText'
    import { watchTheme } from '@/utils/theme'
    import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
    import xcodeCss from 'highlight.js/styles/xcode.css?inline'
    import atomOneDarkCss from 'highlight.js/styles/atom-one-dark.css?inline'

    const props = defineProps<{
        content: string
        /** 用户气泡模式：禁用块级元素（段落间距更紧凑），默认 false */
        inline?: boolean
    }>()

    const rootEl = ref<HTMLElement | null>(null)

    // ── 主题管理（引用计数，多实例安全） ──
    const themeStyles = { light: xcodeCss, dark: atomOneDarkCss }

    const applyTheme = (theme: 'light' | 'dark') => {
        let style = document.getElementById('hljs-theme') as HTMLStyleElement | null
        if (!style) {
            style = document.createElement('style')
            style.id = 'hljs-theme'
            document.head.appendChild(style)
        }
        style.textContent = themeStyles[theme]
    }

    let unwatch: (() => void) | null = null
    onMounted(() => {
        _themeRefCount++
        unwatch = watchTheme((dark) => applyTheme(dark ? 'dark' : 'light'))
    })

    onBeforeUnmount(() => {
        unwatch?.()
        _themeRefCount--
        if (_themeRefCount <= 0) {
            document.getElementById('hljs-theme')?.remove()
            _themeRefCount = 0
        }
    })

    const escapeHtml = MarkdownIt().utils.escapeHtml

    const md: MarkdownIt = new MarkdownIt({
        html: false,
        linkify: true,
        typographer: true,
        breaks: true,
        highlight(str: string, lang: string): string {
            if (lang && hljs.getLanguage(lang)) {
                try {
                    return hljs.highlight(str, { language: lang }).value
                } catch (e) {
                    console.warn('Highlight error:', e)
                }
            }
            return escapeHtml(str)
        },
    })

    md.use(markdownItKatex, {
        throwOnError: false,
        errorColor: '#cc0000',
    })

    // 自定义代码块渲染：添加语言标签和复制按钮
    const defaultFenceRenderer = md.renderer.rules.fence!
    md.renderer.rules.fence = (tokens, idx, options, env, self) => {
        const token = tokens[idx]!
        const lang = token.info?.trim() || 'text'
        const code = defaultFenceRenderer!(tokens, idx, options, env, self)
        // 将代码内容编码为 base64，避免 HTML 属性中的特殊字符问题
        const encodedCode = btoa(unescape(encodeURIComponent(token.content)))

        return `
<div class="code-block-wrapper">
    <div class="code-block-header d-flex align-center justify-space-between">
        <span class="code-block-lang text-caption text-medium-emphasis">${lang}</span>
        <button 
            class="code-copy-btn d-inline-flex align-center px-2 py-1 rounded cursor-pointer bg-transparent border-0 text-medium-emphasis"
            style="height: 24px; transition: background-color 0.2s;"
            data-code="${encodedCode}"
            type="button"
        >
            <svg class="copy-icon" width="14" height="14" viewBox="0 0 24 24" style="margin-right: 4px;">
                <path fill="currentColor" d="M19 21H8a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2m-9-9h9V5h-9m-1 9H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9v9Z"/>
            </svg>
            <span class="text-caption">Copy</span>
        </button>
    </div>
    ${code}
</div>`
    }

    // 对外链强制 noopener + target=_blank
    const defaultLinkRender = md.renderer.rules.link_open ?? (
        (tokens: any[], idx: number, options: any, _env: any, self: any): string => self.renderToken(tokens, idx, options)
    )
    md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
        const token = tokens[idx]!
        token.attrSet('target', '_blank')
        token.attrSet('rel', 'noopener noreferrer')
        return defaultLinkRender(tokens, idx, options, env, self)
    }

    const rendered = computed(() => {
        const raw = props.inline
            ? md.renderInline(props.content)
            : md.render(props.content)
        return DOMPurify.sanitize(raw, {
            ADD_TAGS: [
                // KaTeX
                'math', 'mrow', 'mi', 'mo', 'mn', 'msup', 'msub', 'mfrac',
                'mspace', 'mtext', 'annotation', 'semantics',
                // 代码块复制按钮
                'svg', 'path',
            ],
            ADD_ATTR: [
                'aria-hidden', 'focusable', 'xmlns', 'encoding',
                // svg 属性
                'viewBox', 'fill', 'd', 'width', 'height',
                // 复制按钮
                'data-code',
            ],
        })
    })

    // 复制按钮：通过事件委托处理，无需手动绑定/解绑
    const handleCopy = async (e: Event) => {
        const target = e.target as HTMLElement
        const codeBtn = target.closest('.code-copy-btn')
        if (!codeBtn) return

        const encoded = codeBtn.getAttribute('data-code')
        if (!encoded) return

        const code = decodeURIComponent(escape(atob(encoded)))
        await copyText(code)
    }
</script>

<style>
    /* 全局（非 scoped），让样式能作用到 v-html 渲染的子节点 */

    /* ── 基础文本 ── */
    .md-body {
        line-height: 1.8;
        word-break: break-word;
        overflow-wrap: anywhere;
    }

    .md-body p {
        margin: 0.4em 0;
    }

    .md-body p:first-child {
        margin-top: 0;
    }

    .md-body p:last-child {
        margin-bottom: 0;
    }

    /* ── 标题 ── */
    .md-body h1,
    .md-body h2,
    .md-body h3,
    .md-body h4,
    .md-body h5,
    .md-body h6 {
        margin: 0.6em 0 0.3em;
        font-weight: 600;
        line-height: 1.4;
    }

    .md-body h1 {
        font-size: 1.4em;
    }

    .md-body h2 {
        font-size: 1.2em;
    }

    .md-body h3 {
        font-size: 1.05em;
    }

    .md-body h1:first-child,
    .md-body h2:first-child,
    .md-body h3:first-child {
        margin-top: 0;
    }

    /* ── 列表 ── */
    .md-body ul,
    .md-body ol {
        padding-left: 1.4em;
        margin: 0.3em 0;
    }

    .md-body li {
        margin: 0.15em 0;
    }

    /* ── 行内代码 ── */
    .md-body code {
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
        font-size: 0.87em;
        padding: 0.15em 0.4em;
        border-radius: 4px;
        background: rgba(128, 128, 128, 0.15);
    }

    /* ── 代码块 ── */
    .md-body pre {
        margin: 0;
        padding: 0.8em 1em;
        border-radius: 0 0 8px 8px;
        background: rgba(128, 128, 128, 0.1);
        overflow-x: auto;
    }

    .md-body pre code {
        background: none;
        padding: 0;
        font-size: 0.85em;
    }

    /* ── 代码块包装器（带复制按钮） ── */
    .code-block-wrapper {
        position: relative;
        margin: 0.5em 0;
        border-radius: 8px;
        overflow: hidden;
    }

    .code-block-header {
        padding: 0.4em 0.8em;
        background: rgba(128, 128, 128, 0.08);
        border-bottom: 1px solid rgba(128, 128, 128, 0.1);
    }

    .code-copy-btn {
        color: rgba(var(--v-theme-on-surface), 0.7);
        font-size: 0.75rem;
    }

    .code-copy-btn:hover {
        background-color: rgba(var(--v-theme-on-surface), 0.04) !important;
        color: rgb(var(--v-theme-primary));
    }

    .code-copy-btn:active {
        background-color: rgba(var(--v-theme-on-surface), 0.08) !important;
    }

    /* 深色模式下代码块头部的适配 */
    @media (prefers-color-scheme: dark) {
        .code-block-header {
            background: rgba(255, 255, 255, 0.05);
            border-bottom-color: rgba(255, 255, 255, 0.1);
        }
    }

    .code-block-lang {
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
        font-size: 0.75rem;
        font-weight: 600;
        color: rgba(var(--v-theme-on-surface), 0.6);
        text-transform: lowercase;
    }

    /* ── 引用 ── */
    .md-body blockquote {
        margin: 0.4em 0;
        padding: 0.3em 0.8em;
        border-left: 3px solid rgba(128, 128, 128, 0.4);
        color: rgba(var(--v-theme-on-surface), 0.65);
    }

    /* ── 表格 ── */
    .md-body table {
        border-collapse: collapse;
        margin: 0.5em 0;
        font-size: 0.9em;
        width: max-content;
        max-width: 100%;
    }

    .md-body th,
    .md-body td {
        border: 1px solid rgba(128, 128, 128, 0.3);
        padding: 0.4em 0.8em;
    }

    .md-body th {
        background: rgba(128, 128, 128, 0.1);
        font-weight: 600;
    }

    /* ── 分割线 ── */
    .md-body hr {
        border: none;
        border-top: 1px solid rgba(128, 128, 128, 0.25);
        margin: 0.6em 0;
    }

    /* ── 链接 ── */
    .md-body a {
        color: rgb(var(--v-theme-primary));
        text-decoration: none;
    }

    .md-body a:hover {
        text-decoration: underline;
    }

    /* ── KaTeX 公式对齐修正 ── */
    .md-body .katex-display {
        overflow-x: auto;
        overflow-y: hidden;
        margin: 0.5em 0;
    }
</style>
