import type { RecommendationEngine } from '@/contracts'
import type { PaletteAssessment, PaletteAssessmentRequest, Recommendation, RecommendationRequest } from '@/domain'

type ApiRecommendation = { color: Recommendation['color']; score: number; evidence?: Recommendation['evidence'] }

/** Optional remote adapter. Swap this into runtime.ts when the Python service should own inference. */
export class ApiRecommendationEngine implements RecommendationEngine {
  readonly id: string
  readonly name = 'Wada harmony model'

  constructor(private readonly baseUrl = '/api', engineId = 'group-cooccurrence-v1') {
    this.id = engineId
  }

  async recommend(request: RecommendationRequest): Promise<Recommendation[]> {
    const response = await fetch(`${this.baseUrl}/recommend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        palette_id: request.dataset.metadata.id,
        engine_id: this.id,
        colors: request.selectedColors.map(({ id, name, hex, rgb }) => ({ id, name, hex, rgb })),
        mode: request.mode,
        scope: request.scope,
        limit: request.limit,
      }),
    })
    if (!response.ok) throw new Error(`Recommendation service failed (${response.status})`)
    const payload = await response.json() as { recommendations: ApiRecommendation[] }
    return payload.recommendations
  }

  async assess(request: PaletteAssessmentRequest): Promise<PaletteAssessment | null> {
    const response = await fetch(`${this.baseUrl}/assess`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        palette_id: request.dataset.metadata.id,
        engine_id: this.id,
        colors: request.selectedColors.map(({ id, name, hex, rgb }) => ({ id, name, hex, rgb })),
      }),
    })
    if (!response.ok) throw new Error(`Palette assessment failed (${response.status})`)
    const payload = await response.json() as { assessment: PaletteAssessment | null }
    return payload.assessment
  }
}
