export const LOGIN_PATH = '/auth'

export function normalizeReturnTo(value: unknown, fallback = '/'): string {
  if (typeof value !== 'string' || !value) {
    return fallback
  }

  try {
    const decoded = decodeURIComponent(value)
    if (!decoded.startsWith('/') || decoded.startsWith('//')) {
      return fallback
    }

    return decoded
  } catch {
    return fallback
  }
}
