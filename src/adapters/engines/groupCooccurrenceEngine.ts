import type { RecommendationEngine } from '../../contracts/recommendationEngine'
import type { Recommendation, RecommendationRequest } from '../../domain/palette'
import { rgbDistance } from '../../lib/colorMath'

/** Explainable baseline engine for palettes with color-to-group training signals. */
export class GroupCooccurrenceEngine implements RecommendationEngine {
  readonly id = 'group-cooccurrence-v1'
  readonly name = 'Group co-occurrence'

  async recommend({ dataset, selectedColorIds, mode, limit }: RecommendationRequest): Promise<Recommendation[]> {
    if (selectedColorIds.length === 0) return []
    const selectedIds = new Set(selectedColorIds)
    const colorsById = new Map(dataset.colors.map((color) => [color.id, color]))
    const selected = selectedColorIds.flatMap((id) => {
      const color = colorsById.get(id)
      return color ? [color] : []
    })
    const observedGroups = new Set(selectedColorIds.flatMap((id) => dataset.groupsByColor[id] ?? []))

    const scored = dataset.colors.flatMap((color): Recommendation[] => {
      if (selectedIds.has(color.id)) return []
      const groups = dataset.groupsByColor[color.id] ?? []
      const shared = groups.reduce((count, groupId) => count + Number(observedGroups.has(groupId)), 0)
      if (shared === 0) return []
      const coOccurrence = shared / Math.sqrt(Math.max(1, groups.length * observedGroups.size))
      const distance = selected.reduce((sum, input) => sum + rgbDistance(color, input), 0) / selected.length
      const moodFactor = mode === 'quiet' ? 1 - distance : mode === 'vivid' ? distance : 1 - Math.abs(distance - 0.52)
      return [{ color, score: coOccurrence * 0.82 + moodFactor * 0.18, evidence: { label: 'shared', value: shared } }]
    })

    return scored.sort((left, right) => right.score - left.score).slice(0, limit)
  }
}
