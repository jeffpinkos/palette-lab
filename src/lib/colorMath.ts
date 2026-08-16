import type { PaletteColor } from '../domain/palette'

const HEX_PATTERN = /^#[0-9a-f]{6}$/i

export function closestColor(colors: PaletteColor[], hex: string) {
  const normalized = hex.startsWith('#') ? hex : `#${hex}`
  if (!HEX_PATTERN.test(normalized) || colors.length === 0) return null
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
