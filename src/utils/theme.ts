export type ThemePreference = 'system' | 'light' | 'dark'

const THEME_STORAGE_KEY = 'opencrab:theme-preference'
const THEME_PREFERENCES: readonly ThemePreference[] = ['system', 'light', 'dark']

function canUseLocalStorage () {
    return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function normalizeThemePreference (value: unknown): ThemePreference {
    return THEME_PREFERENCES.includes(value as ThemePreference)
        ? value as ThemePreference
        : 'system'
}

export function getStoredThemePreference (): ThemePreference {
    if (!canUseLocalStorage()) return 'system'
    return normalizeThemePreference(window.localStorage.getItem(THEME_STORAGE_KEY))
}

export function setStoredThemePreference (preference: ThemePreference) {
    if (!canUseLocalStorage()) return
    window.localStorage.setItem(THEME_STORAGE_KEY, preference)
}

/**
 * 监听系统主题变化。
 * 用于不在 Vuetify 组件树内的代码；组件内优先使用 useTheme().current.value.dark。
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
