import type { PaletteAssessment, PaletteAssessmentRequest, Recommendation, RecommendationRequest } from '../domain/palette'

export interface RecommendationEngine {
  readonly id: string
  readonly name: string
  recommend(request: RecommendationRequest): Promise<Recommendation[]>
  assess?(request: PaletteAssessmentRequest): Promise<PaletteAssessment | null>
}
