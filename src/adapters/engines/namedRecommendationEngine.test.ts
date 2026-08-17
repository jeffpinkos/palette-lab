import { describe, expect, it, vi } from 'vitest'
import type { ColorNamer } from '@/contracts'
import type { RecommendationEngine } from '@/contracts'
import type { RecommendationRequest } from '@/domain'
import { NamedRecommendationEngine } from './namedRecommendationEngine'

const request: RecommendationRequest = {
  dataset: { metadata: { id: 'test', name: 'Test', description: '', sourceName: 'Test', groupLabel: 'groups' }, colors: [], groupsByColor: {}, groupCount: 0 },
  selectedColors: [], mode: 'balanced', scope: 'spectrum', limit: 2,
}
const generated = { id: 'generated:1', name: 'Spectrum blue', hex: '#123456', rgb: [18, 52, 86] as [number, number, number], metadata: { generated: true } }
const archive = { id: 'archive:1', name: 'Archive red', hex: '#cc2233', rgb: [204, 34, 51] as [number, number, number] }
const assessment = { grade: 'C', score: 61, label: 'Wada-adjacent', summary: 'Some support.', details: [] }

const setup = () => {
  const recommend = vi.fn().mockResolvedValue([{ color: generated, score: .8 }, { color: archive, score: .6 }])
  const assess = vi.fn().mockResolvedValue(assessment)
  const engine: RecommendationEngine = { id: 'model-v2', name: 'Test model', recommend, assess }
  const name = vi.fn(async (color) => color === generated ? { ...color, name: 'Incremental Blue' } : color)
  const namer: ColorNamer = { count: 31_914, prepare: vi.fn(), name, search: vi.fn() }
  return { decorated: new NamedRecommendationEngine(engine, namer), recommend, assess, name }
}

describe('NamedRecommendationEngine', () => {
  it('preserves the underlying engine identity', () => {
    const { decorated } = setup()
    expect({ id: decorated.id, name: decorated.name }).toEqual({ id: 'model-v2', name: 'Test model' })
  })

  it('forwards the complete recommendation request', async () => {
    const { decorated, recommend } = setup()
    await decorated.recommend(request)
    expect(recommend).toHaveBeenCalledWith(request)
  })

  it('names every returned recommendation without changing its score', async () => {
    const { decorated, name } = setup()
    const results = await decorated.recommend(request)
    expect(name).toHaveBeenCalledTimes(2)
    expect(results).toEqual([
      { color: expect.objectContaining({ name: 'Incremental Blue' }), score: .8 },
      { color: archive, score: .6 },
    ])
  })

  it('does not mutate the underlying recommendation colors', async () => {
    const { decorated } = setup()
    await decorated.recommend(request)
    expect(generated.name).toBe('Spectrum blue')
    expect(archive.name).toBe('Archive red')
  })

  it('forwards palette assessment without invoking the color namer', async () => {
    const { decorated, assess, name } = setup()
    await expect(decorated.assess({ dataset: request.dataset, selectedColors: request.selectedColors })).resolves.toEqual(assessment)
    expect(assess).toHaveBeenCalledWith({ dataset: request.dataset, selectedColors: request.selectedColors })
    expect(name).not.toHaveBeenCalled()
  })

  it('returns no assessment when the wrapped engine does not provide one', async () => {
    const engine: RecommendationEngine = { id: 'x', name: 'X', recommend: vi.fn().mockResolvedValue([]) }
    const namer: ColorNamer = { count: 0, prepare: vi.fn(), name: vi.fn(), search: vi.fn() }
    await expect(new NamedRecommendationEngine(engine, namer).assess({ dataset: request.dataset, selectedColors: [] })).resolves.toBeNull()
  })

  it('propagates underlying engine failures', async () => {
    const failure = new Error('model offline')
    const engine: RecommendationEngine = { id: 'x', name: 'X', recommend: vi.fn().mockRejectedValue(failure) }
    const namer: ColorNamer = { count: 0, prepare: vi.fn(), name: vi.fn(), search: vi.fn() }
    await expect(new NamedRecommendationEngine(engine, namer).recommend(request)).rejects.toBe(failure)
  })
})
