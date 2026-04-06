/**
 * 复制文本到剪贴板（带回调）
 * @param text 要复制的文本
 * @param callbacks 可选的回调函数
 * @param callbacks.onSuccess 复制成功时的回调
 * @param callbacks.onError 复制失败时的回调
 */
export const copyText = async (
    text: string,
    callbacks?: {
        onSuccess?: () => void
        onError?: (err: unknown) => void
    }
) => {
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text)
        } else {
            // Fallback: 使用传统的 execCommand 方法
            const textarea = document.createElement('textarea')
            textarea.value = text
            textarea.style.position = 'fixed'
            textarea.style.opacity = '0'
            document.body.appendChild(textarea)
            textarea.select()
            document.execCommand('copy')
            document.body.removeChild(textarea)
        }
        callbacks?.onSuccess?.()
    } catch (e) {
        console.error('copy failed', e)
        callbacks?.onError?.(e)
    }
}