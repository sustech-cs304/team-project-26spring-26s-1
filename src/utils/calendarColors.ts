export interface CalendarColorOption {
    label: string
    hex: string
}

export const CALENDAR_COLOR_OPTIONS: CalendarColorOption[] = [
    { label: 'Red', hex: '#ed201d' },
    { label: 'Orange', hex: '#fd7941' },
    { label: 'Yellow', hex: '#f4be40' },
    { label: 'Green', hex: '#5ecc89' },
    { label: 'Blue', hex: '#4ca8df' },
    { label: 'Purple', hex: '#985df6' },
    { label: 'Gray', hex: '#b8b8b8' },
]

export const DEFAULT_CALENDAR_COLOR = '#4ca8df'
const DEFAULT_CALENDAR_COLOR_OPTION: CalendarColorOption = { label: 'Blue', hex: DEFAULT_CALENDAR_COLOR }

const expandHex = (value: string) => (
    value.length === 4
        ? `#${value[1]}${value[1]}${value[2]}${value[2]}${value[3]}${value[3]}`
        : value
)

const normalizeHexString = (value?: string | null): string => {
    const raw = `${value ?? ''}`.trim()
    if (!/^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(raw)) return ''
    return expandHex(raw).toLowerCase()
}

const hexToRgb = (hex: string) => ({
    r: Number.parseInt(hex.slice(1, 3), 16),
    g: Number.parseInt(hex.slice(3, 5), 16),
    b: Number.parseInt(hex.slice(5, 7), 16),
})

const colorDistance = (a: string, b: string) => {
    const left = hexToRgb(a)
    const right = hexToRgb(b)
    return ((left.r - right.r) ** 2) + ((left.g - right.g) ** 2) + ((left.b - right.b) ** 2)
}

const closestPaletteColor = (normalized: string): string => {
    const exact = CALENDAR_COLOR_OPTIONS.find(option => option.hex.toLowerCase() === normalized)
    if (exact) return exact.hex

    return CALENDAR_COLOR_OPTIONS.reduce<CalendarColorOption>((closest, option) => (
        colorDistance(normalized, option.hex) < colorDistance(normalized, closest.hex)
            ? option
            : closest
    ), CALENDAR_COLOR_OPTIONS[0] ?? DEFAULT_CALENDAR_COLOR_OPTION).hex
}

export const normalizeCalendarColor = (value?: string | null, fallback = DEFAULT_CALENDAR_COLOR): string => {
    const normalized = normalizeHexString(value)
    if (normalized) return closestPaletteColor(normalized)

    const normalizedFallback = normalizeHexString(fallback)
    return normalizedFallback ? closestPaletteColor(normalizedFallback) : DEFAULT_CALENDAR_COLOR
}

export const getCalendarColorLabel = (value?: string | null): string => {
    const normalized = normalizeCalendarColor(value)
    return CALENDAR_COLOR_OPTIONS.find(option => option.hex === normalized)?.label ?? 'Blue'
}
