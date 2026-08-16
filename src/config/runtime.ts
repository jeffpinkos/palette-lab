import type { PaletteProvider } from '../contracts/paletteProvider'
import type { RecommendationEngine } from '../contracts/recommendationEngine'
import type { ColorNamer } from '../contracts/colorNamer'
import { ApiRecommendationEngine } from '../adapters/engines/apiRecommendationEngine'
import { NamedRecommendationEngine } from '../adapters/engines/namedRecommendationEngine'
import { ColorNameListNamer } from '../adapters/names/colorNameListNamer'
import { WadaPaletteProvider } from '../adapters/palettes/wadaPaletteProvider'

export type LabRuntime = {
  paletteProvider: PaletteProvider
  recommendationEngine: RecommendationEngine
  colorNamer: ColorNamer
  maxSelections: number
  resultLimit: number
}

/** Composition root: change adapters here without touching the React feature. */
const colorNamer = new ColorNameListNamer()

export const runtime: LabRuntime = {
  paletteProvider: new WadaPaletteProvider(),
  recommendationEngine: new NamedRecommendationEngine(new ApiRecommendationEngine('/api', 'cluster-ensemble-v2'), colorNamer),
  colorNamer,
  maxSelections: 4,
  resultLimit: 4,
}
