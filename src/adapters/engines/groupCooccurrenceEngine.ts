import type { RecommendationEngine } from '../../contracts/recommendationEngine'
import type { Recommendation, RecommendationRequest } from '../../domain/palette'
import { perceptualDistance } from '../../lib/colorMath'

/** Explainable baseline engine for palettes with color-to-group training signals. */
export class GroupCooccurrenceEngine implements RecommendationEngine {
  readonly id = 'group-cooccurrence-v1'
  readonly name = 'Group co-occurrence'

  async recommend({ dataset, selectedColors, mode, limit }: RecommendationRequest): Promise<Recommendation[]> {
    if (selectedColors.length === 0) return []
    const colorsById = new Map(dataset.colors.map((color) => [color.id, color]))
    const anchors = selectedColors.flatMap((selected) => {
      const known = colorsById.get(selected.id)
      if (known) return [known]
      const nearest = dataset.colors.reduce<{ color: typeof selected | null; distance: number }>((best, candidate) => {
        const distance = perceptualDistance(selected, candidate)
        return distance < best.distance ? { color: candidate, distance } : best
      }, { color: null, distance: Number.POSITIVE_INFINITY }).color
      return nearest ? [nearest] : []
    })
    if (anchors.length === 0) return []
    const excludedIds = new Set([...selectedColors.map((color) => color.id), ...anchors.map((color) => color.id)])
    const observedGroups = new Set(anchors.flatMap((color) => dataset.groupsByColor[color.id] ?? []))

    const scored = dataset.colors.flatMap((color): Recommendation[] => {
      if (excludedIds.has(color.id)) return []
      const groups = dataset.groupsByColor[color.id] ?? []
      const shared = groups.reduce((count, groupId) => count + Number(observedGroups.has(groupId)), 0)
      if (shared === 0) return []
      const coOccurrence = shared / Math.sqrt(Math.max(1, groups.length * observedGroups.size))
      const distance = selectedColors.reduce((sum, input) => sum + perceptualDistance(color, input), 0) / selectedColors.length
      const moodFactor = mode === 'quiet' ? 1 - distance : mode === 'vivid' ? distance : 1 - Math.abs(distance - 0.52)
      const noun = shared === 1 ? 'group' : 'groups'
      return [{ color, score: coOccurrence * 0.82 + moodFactor * 0.18, evidence: { label: `shared ${noun}`, value: shared, details: [`Appears with the selection in ${shared} palette ${noun}`] } }]
    })

    return scored.sort((left, right) => right.score - left.score).slice(0, limit)
  }
}
