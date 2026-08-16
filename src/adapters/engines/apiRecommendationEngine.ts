import type { RecommendationEngine } from '../../contracts/recommendationEngine'
import type { Recommendation, RecommendationRequest } from '../../domain/palette'

type ApiRecommendation = { color: Recommendation['color']; score: number; evidence?: Recommendation['evidence'] }

/** Optional remote adapter. Swap this into runtime.ts when the Python service should own inference. */
export class ApiRecommendationEngine implements RecommendationEngine {
  readonly id: string
  readonly name = 'Remote ML service'

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
        color_ids: request.selectedColorIds,
        mode: request.mode,
        limit: request.limit,
      }),
    })
    if (!response.ok) throw new Error(`Recommendation service failed (${response.status})`)
    const payload = await response.json() as { recommendations: ApiRecommendation[] }
    return payload.recommendations
  }
}
