import type { PaletteProvider } from '../../contracts/paletteProvider'
import type { PaletteDataset } from '../../domain/palette'

type WadaColor = {
  index: number
  name: string
  hex: string
  rgb_array: [number, number, number]
  combinations: number[]
  use_count: number
}

type WadaPayload = { colors: WadaColor[] }
const normalizeDisplayName = (name: string) => name.replace(/\bBLue\b/g, 'Blue')

export class WadaPaletteProvider implements PaletteProvider {
  readonly id = 'wada-1933'

  constructor(private readonly sourceUrl = '/colors.json') {}

  async load(): Promise<PaletteDataset> {
    const response = await fetch(this.sourceUrl)
    if (!response.ok) throw new Error(`Unable to load Wada palette (${response.status})`)
    const payload = await response.json() as WadaPayload
    const colors = payload.colors.map((color) => ({
      id: String(color.index),
      name: normalizeDisplayName(color.name),
      hex: color.hex,
      rgb: color.rgb_array,
      metadata: { sourceIndex: color.index, useCount: color.use_count },
    }))

    return {
      metadata: {
        id: this.id,
        name: 'WADA',
        description: 'Choose up to four starting colors. Wada studies the company they keep.',
        sourceName: 'Sanzo Wada',
        sourceUrl: 'https://sanzo-wada.dmbk.io/',
        attribution: 'Sanzo Wada · 1933',
        editionLabel: '348 combinations',
        groupLabel: 'historic combinations',
      },
      colors,
      groupsByColor: Object.fromEntries(payload.colors.map((color) => [String(color.index), color.combinations.map(String)])),
      groupCount: 348,
      defaultColorIds: ['19', '112'],
    }
  }
}
