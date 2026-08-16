import type { PaletteColor } from '../domain/palette'

const HEX_PATTERN = /^#[0-9a-f]{6}$/i

export function normalizeHex(hex: string) {
  const normalized = hex.startsWith('#') ? hex : `#${hex}`
  return HEX_PATTERN.test(normalized) ? normalized.toLowerCase() : null
}

export function colorFromHex(colors: PaletteColor[], hex: string): PaletteColor | null {
  const normalized = normalizeHex(hex)
  if (!normalized) return null
  const known = colors.find((color) => color.hex.toLowerCase() === normalized)
  if (known) return known
  const value = normalized.slice(1)
  const rgb = [0, 2, 4].map((offset) => parseInt(value.slice(offset, offset + 2), 16)) as [number, number, number]
  return { id: `custom:${normalized}`, name: 'Custom color', hex: normalized, rgb, metadata: { custom: true } }
}

export function closestColor(colors: PaletteColor[], hex: string) {
  const normalized = normalizeHex(hex)
  if (!normalized || colors.length === 0) return null
  const value = normalized.slice(1)
  const rgb = [0, 2, 4].map((offset) => parseInt(value.slice(offset, offset + 2), 16))
  return colors.reduce((closest, color) => {
    const distance = color.rgb.reduce((sum, channel, index) => sum + (channel - rgb[index]) ** 2, 0)
    return distance < closest.distance ? { color, distance } : closest
  }, { color: colors[0], distance: Number.POSITIVE_INFINITY }).color
}

export function rgbDistance(left: PaletteColor, right: PaletteColor) {
  return Math.sqrt(left.rgb.reduce((sum, channel, index) => sum + (channel - right.rgb[index]) ** 2, 0)) / 441.67
}
