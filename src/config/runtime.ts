import type { PaletteProvider } from '../contracts/paletteProvider'
import type { RecommendationEngine } from '../contracts/recommendationEngine'
import { ApiRecommendationEngine } from '../adapters/engines/apiRecommendationEngine'
import { WadaPaletteProvider } from '../adapters/palettes/wadaPaletteProvider'

export type LabRuntime = {
  paletteProvider: PaletteProvider
  recommendationEngine: RecommendationEngine
  maxSelections: number
  resultLimit: number
}

/** Composition root: change adapters here without touching the React feature. */
export const runtime: LabRuntime = {
  paletteProvider: new WadaPaletteProvider(),
  recommendationEngine: new ApiRecommendationEngine('/api', 'cluster-ensemble-v1'),
  maxSelections: 4,
  resultLimit: 4,
}
