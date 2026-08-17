import type { PaletteColor } from '@/domain'

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
    const distance = perceptualDistance({ ...color, rgb: color.rgb }, { id: '', name: '', hex: normalized, rgb: rgb as [number, number, number] })
    return distance < closest.distance ? { color, distance } : closest
  }, { color: colors[0], distance: Number.POSITIVE_INFINITY }).color
}

export function rgbDistance(left: PaletteColor, right: PaletteColor) {
  return Math.sqrt(left.rgb.reduce((sum, channel, index) => sum + (channel - right.rgb[index]) ** 2, 0)) / 441.67
}

const linearChannel = (channel: number) => {
  const value = channel / 255
  return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
}

export function rgbToOklab(color: PaletteColor): [number, number, number] {
  const [red, green, blue] = color.rgb.map(linearChannel)
  const l = 0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue
  const m = 0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue
  const s = 0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue
  const [lRoot, mRoot, sRoot] = [Math.cbrt(l), Math.cbrt(m), Math.cbrt(s)]
  return [
    0.2104542553 * lRoot + 0.793617785 * mRoot - 0.0040720468 * sRoot,
    1.9779984951 * lRoot - 2.428592205 * mRoot + 0.4505937099 * sRoot,
    0.0259040371 * lRoot + 0.7827717662 * mRoot - 0.808675766 * sRoot,
  ]
}

export function perceptualDistance(left: PaletteColor, right: PaletteColor) {
  const leftLab = rgbToOklab(left)
  const rightLab = rgbToOklab(right)
  const raw = Math.sqrt(leftLab.reduce((sum, channel, index) => sum + (channel - rightLab[index]) ** 2, 0))
  return Math.min(1, raw / 0.75)
}
