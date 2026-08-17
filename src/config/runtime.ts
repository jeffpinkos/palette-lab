import type { PaletteProvider } from '@/contracts'
import type { RecommendationEngine } from '@/contracts'
import type { ColorNamer } from '@/contracts'
import { ApiRecommendationEngine } from '@/adapters/engines'
import { NamedRecommendationEngine } from '@/adapters/engines'
import { ColorNameListNamer } from '@/adapters/names'
import { WadaPaletteProvider } from '@/adapters/palettes'

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
