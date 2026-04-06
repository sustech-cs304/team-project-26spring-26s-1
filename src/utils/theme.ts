/**
 * 监听系统主题变化
 * @param callback 主题变化时的回调函数 (isDark: boolean)
 * @returns 取消监听的函数
 */
export function watchTheme(callback: (isDark: boolean) => void): () => void {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    
    // 初始调用
    callback(mediaQuery.matches)
    
    // 监听变化
    const handler = (e: MediaQueryListEvent) => {
        callback(e.matches)
    }
    
    mediaQuery.addEventListener('change', handler)
    
    // 返回取消监听的函数
    return () => {
        mediaQuery.removeEventListener('change', handler)
    }
}

/**
 * 判断当前是否为深色模式
 */
export const isDarkMode = (): boolean => {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
}
