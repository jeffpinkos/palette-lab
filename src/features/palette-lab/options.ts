import type { HarmonyMode, RecommendationScope } from '@/domain'

export const HARMONY_MODES: HarmonyMode[] = ['quiet', 'balanced', 'vivid']

export const MODE_COPY: Record<HarmonyMode, string> = {
  quiet: 'Neighboring hues, restrained chroma, and gentle value shifts.',
  balanced: 'Measured hue intervals with useful light–dark contrast.',
  vivid: 'Higher chroma, wider hue intervals, and stronger contrast.',
}

export const RECOMMENDATION_SCOPES: { value: RecommendationScope; label: string }[] = [
  { value: 'companions', label: 'Wada companions' },
  { value: 'palette', label: 'Wada archive' },
  { value: 'spectrum', label: 'Full spectrum' },
]
