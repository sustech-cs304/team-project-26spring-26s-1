<template>
    <div class="md-body" v-html="rendered" />
</template>

<script setup lang="ts">
    import MarkdownIt from 'markdown-it'
    import markdownItKatex from '@vscode/markdown-it-katex'
    import DOMPurify from 'dompurify'

    const props = defineProps<{
        content: string
        /** 用户气泡模式：禁用块级元素（段落间距更紧凑），默认 false */
        inline?: boolean
    }>()

    const md = new MarkdownIt({
        html: false,       // 禁止原始 HTML 输入，安全第一
        linkify: true,     // 自动识别 URL
        typographer: true, // 引号、破折号等排版优化
        breaks: true,      // 单个换行视为 <br>
    })

    md.use(markdownItKatex, {
        throwOnError: false,
        errorColor: '#cc0000',
    })

    // 对外链强制 noopener + target=_blank
    const defaultRender = md.renderer.rules.link_open ?? (
        (tokens: any[], idx: number, options: any, _env: any, self: any) => self.renderToken(tokens, idx, options)
    )
    md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
        const token = tokens[idx]!
        token.attrSet('target', '_blank')
        token.attrSet('rel', 'noopener noreferrer')
        return defaultRender(tokens, idx, options, env, self)
    }

    const rendered = computed(() => {
        const raw = props.inline
            ? md.renderInline(props.content)
            : md.render(props.content)
        return DOMPurify.sanitize(raw, {
            // 允许 KaTeX 输出的标签和属性
            ADD_TAGS: ['math', 'mrow', 'mi', 'mo', 'mn', 'msup', 'msub', 'mfrac',
                'mspace', 'mtext', 'annotation', 'semantics'],
            ADD_ATTR: ['aria-hidden', 'focusable', 'xmlns', 'encoding'],
        })
    })
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
        border-radius: 8px;
        background: rgba(128, 128, 128, 0.1);
        overflow-x: auto;
    }

    .md-body pre code {
        background: none;
        padding: 0;
        font-size: 0.85em;
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
