import type { PaletteProvider } from '../contracts/paletteProvider'
import type { RecommendationEngine } from '../contracts/recommendationEngine'
import { GroupCooccurrenceEngine } from '../adapters/engines/groupCooccurrenceEngine'
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
  recommendationEngine: new GroupCooccurrenceEngine(),
  maxSelections: 4,
  resultLimit: 4,
}
