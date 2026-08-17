import type { ColorNamer } from '@/contracts'
import type { PaletteColor } from '@/domain'
import { rgbToOklab } from '@/lib'

type NameRecord = { name: string; hex: string }
type PreparedName = NameRecord & {
  rgb: [number, number, number]
  lab: [number, number, number]
  searchableName: string
}

type PreparedCatalog = {
  colors: PreparedName[]
  exactByHex: Map<string, PreparedName>
}

const CATALOG_SIZE = 31_914
let catalogPromise: Promise<PreparedCatalog> | null = null

const normalizeText = (value: string) => value
  .normalize('NFKD')
  .replace(/\p{Mark}/gu, '')
  .toLocaleLowerCase()
  .trim()

const rgbFromHex = (hex: string) => [0, 2, 4].map((offset) => Number.parseInt(hex.slice(1 + offset, 3 + offset), 16)) as [number, number, number]

const prepareCatalog = async (): Promise<PreparedCatalog> => {
  const { colornames } = await import('color-name-list')
  const colors = (colornames as NameRecord[]).map(({ name, hex }) => {
    const normalizedHex = hex.toLocaleLowerCase()
    const rgb = rgbFromHex(normalizedHex)
    return {
      name,
      hex: normalizedHex,
      rgb,
      lab: rgbToOklab({ id: normalizedHex, name, hex: normalizedHex, rgb }),
      searchableName: normalizeText(name),
    }
  })
  return { colors, exactByHex: new Map(colors.map((color) => [color.hex, color])) }
}

const loadCatalog = () => {
  catalogPromise ??= prepareCatalog()
  return catalogPromise
}

const squaredDistance = (left: [number, number, number], right: [number, number, number]) => left.reduce((sum, value, index) => sum + (value - right[index]) ** 2, 0)

const closestName = (colors: PreparedName[], targetLab: [number, number, number]) => colors.reduce((closest, candidate) => {
  const distance = squaredDistance(candidate.lab, targetLab)
  return distance < closest.distance ? { color: candidate, distance } : closest
}, { color: colors[0], distance: Number.POSITIVE_INFINITY }).color

const shouldName = (color: PaletteColor) => Boolean(
  color.metadata?.custom
  || color.metadata?.generated
  || color.name === 'Custom color'
  || color.name.startsWith('Spectrum '),
)

const asPaletteColor = (color: PreparedName): PaletteColor => ({
  id: `named:${color.hex}`,
  name: color.name,
  hex: color.hex,
  rgb: color.rgb,
  metadata: { named: true, nameSource: 'Color Name List' },
})

export class ColorNameListNamer implements ColorNamer {
  readonly count = CATALOG_SIZE

  async prepare() {
    await loadCatalog()
  }

  async name(color: PaletteColor) {
    if (!shouldName(color)) return color
    const catalog = await loadCatalog()
    const exact = catalog.exactByHex.get(color.hex.toLocaleLowerCase())
    const targetLab = rgbToOklab(color)
    const match = exact ?? closestName(catalog.colors, targetLab)
    const distance = Math.sqrt(squaredDistance(match.lab, targetLab))
    return {
      ...color,
      name: match.name,
      metadata: {
        ...color.metadata,
        nameSource: 'Color Name List',
        nameMatchHex: match.hex,
        nameDistance: distance,
      },
    }
  }

  async search(query: string, limit = 8) {
    const normalizedQuery = normalizeText(query)
    if (!normalizedQuery || limit <= 0) return []
    const { colors } = await loadCatalog()
    return colors
      .flatMap((color) => {
        const index = color.searchableName.indexOf(normalizedQuery)
        if (index < 0 && !color.hex.includes(normalizedQuery)) return []
        const rank = color.searchableName === normalizedQuery ? 0
          : color.searchableName.startsWith(normalizedQuery) ? 1
            : color.searchableName.split(/\s+/).some((word) => word.startsWith(normalizedQuery)) ? 2
              : 3
        return [{ color, rank, index }]
      })
      .sort((left, right) => left.rank - right.rank
        || left.index - right.index
        || left.color.name.length - right.color.name.length
        || left.color.name.localeCompare(right.color.name))
      .slice(0, limit)
      .map(({ color }) => asPaletteColor(color))
  }
}
