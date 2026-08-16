import type { Recommendation, RecommendationRequest } from '../domain/palette'

export interface RecommendationEngine {
  readonly id: string
  readonly name: string
  recommend(request: RecommendationRequest): Promise<Recommendation[]>
}
