export type ColorId = string
export type HarmonyMode = 'quiet' | 'balanced' | 'vivid'
export type RecommendationScope = 'palette' | 'spectrum'

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
  evidence?: { label: string; value: number; details?: string[] }
}

export type PaletteAssessment = {
  grade: string
  score: number | null
  label: string
  summary: string
  details: string[]
}

export type RecommendationRequest = {
  dataset: PaletteDataset
  selectedColors: PaletteColor[]
  mode: HarmonyMode
  scope: RecommendationScope
  limit: number
}

export type PaletteAssessmentRequest = {
  dataset: PaletteDataset
  selectedColors: PaletteColor[]
}
