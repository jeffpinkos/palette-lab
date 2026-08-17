import type { HarmonyMode, PaletteColor, RecommendationScope } from '@/domain'

const COOKIE_NAME = 'wada-last-palette'
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30

type StoredColor = Pick<PaletteColor, 'id' | 'name' | 'hex' | 'rgb'>

export type PaletteSession = {
  version: 1
  colors: StoredColor[]
  mode: HarmonyMode
  scope: RecommendationScope
}

const isMode = (value: unknown): value is HarmonyMode => value === 'quiet' || value === 'balanced' || value === 'vivid'
const isScope = (value: unknown): value is RecommendationScope => value === 'companions' || value === 'palette' || value === 'spectrum'
const isColor = (value: unknown): value is StoredColor => {
  if (!value || typeof value !== 'object') return false
  const color = value as Partial<StoredColor>
  return typeof color.id === 'string' && typeof color.name === 'string'
    && typeof color.hex === 'string' && /^#[0-9a-f]{6}$/i.test(color.hex)
    && Array.isArray(color.rgb) && color.rgb.length === 3 && color.rgb.every((channel) => Number.isInteger(channel) && channel >= 0 && channel <= 255)
}

export const parsePaletteSession = (value: string | undefined): PaletteSession | null => {
  if (!value) return null
  try {
    const parsed = JSON.parse(decodeURIComponent(value)) as Partial<PaletteSession>
    if (parsed.version !== 1 || !isMode(parsed.mode) || !isScope(parsed.scope) || !Array.isArray(parsed.colors) || !parsed.colors.every(isColor)) return null
    return { version: 1, colors: parsed.colors, mode: parsed.mode, scope: parsed.scope }
  } catch {
    return null
  }
}

export const paletteSessionFromCookie = (cookie: string): PaletteSession | null => {
  const value = cookie.split('; ').find((entry) => entry.startsWith(`${COOKIE_NAME}=`))?.slice(COOKIE_NAME.length + 1)
  return parsePaletteSession(value)
}

export const readPaletteSession = (): PaletteSession | null => typeof document === 'undefined' ? null : paletteSessionFromCookie(document.cookie)

export const savePaletteSession = (session: Omit<PaletteSession, 'version'>) => {
  if (typeof document === 'undefined') return
  const colors = session.colors.map(({ id, name, hex, rgb }) => ({ id, name, hex, rgb }))
  const value = encodeURIComponent(JSON.stringify({ version: 1, colors, mode: session.mode, scope: session.scope }))
  document.cookie = `${COOKIE_NAME}=${value}; Max-Age=${COOKIE_MAX_AGE_SECONDS}; Path=/; SameSite=Lax`
}
