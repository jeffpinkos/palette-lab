export type ColorId = string
export type HarmonyMode = 'quiet' | 'balanced' | 'vivid'

export type PaletteColor = {
  id: ColorId
  name: string
  hex: string
  rgb: [number, number, number]
  metadata?: Record<string, unknown>
}

export type PaletteMetadata = {
  id: string
  name: string
  description: string
  sourceName: string
  sourceUrl?: string
  attribution?: string
  editionLabel?: string
  groupLabel: string
}

export type PaletteDataset = {
  metadata: PaletteMetadata
  colors: PaletteColor[]
  /** Optional model-training signals. Engines that do not need groups can ignore them. */
  groupsByColor: Record<ColorId, string[]>
  groupCount: number
  defaultColorIds?: ColorId[]
}

export type Recommendation = {
  color: PaletteColor
  score: number
  evidence?: { label: string; value: number }
}

export type RecommendationRequest = {
  dataset: PaletteDataset
  selectedColors: PaletteColor[]
  mode: HarmonyMode
  limit: number
}
