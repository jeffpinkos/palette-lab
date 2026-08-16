import type { ColorNamer } from '../../contracts/colorNamer'
import type { RecommendationEngine } from '../../contracts/recommendationEngine'
import type { RecommendationRequest } from '../../domain/palette'

/** Decorates generated recommendations with friendly names while preserving source-palette labels. */
export class NamedRecommendationEngine implements RecommendationEngine {
  readonly id: string
  readonly name: string

  constructor(private readonly engine: RecommendationEngine, private readonly namer: ColorNamer) {
    this.id = engine.id
    this.name = engine.name
  }

  async recommend(request: RecommendationRequest) {
    const recommendations = await this.engine.recommend(request)
    return Promise.all(recommendations.map(async (recommendation) => ({
      ...recommendation,
      color: await this.namer.name(recommendation.color),
    })))
  }
}
