import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiRecommendationEngine } from './apiRecommendationEngine'
import type { RecommendationRequest } from '@/domain'

const request: RecommendationRequest = {
  dataset: {
    metadata: { id: 'palette-x', name: 'X', description: '', sourceName: 'Test', groupLabel: 'sets' },
    colors: [], groupsByColor: {}, groupCount: 0,
  },
  selectedColors: [
    { id: 'red', name: 'Red', hex: '#ff0000', rgb: [255, 0, 0] },
    { id: 'custom:#123456', name: 'Custom color', hex: '#123456', rgb: [18, 52, 86] },
  ], mode: 'vivid', scope: 'spectrum', limit: 6,
}
const recommendation = { color: { id: 'green', name: 'Green', hex: '#00ff00', rgb: [0, 255, 0] }, score: .88, evidence: { label: 'neighbors', value: 12 } }
const assessment = { grade: 'B', score: 74, label: 'Strong Wada affinity', summary: 'Well supported.', details: ['Historic evidence'] }
const response = (body: unknown, ok = true, status = 200) => ({ ok, status, json: vi.fn().mockResolvedValue(body) })

afterEach(() => vi.unstubAllGlobals())

describe('ApiRecommendationEngine', () => {
  it('uses the default engine identity', () => expect(new ApiRecommendationEngine().id).toBe('group-cooccurrence-v1'))
  it('accepts another remote engine identity', () => expect(new ApiRecommendationEngine('/ml', 'embedding-v2').id).toBe('embedding-v2'))
  it('uses an artist-facing model name', () => expect(new ApiRecommendationEngine().name).toBe('Wada harmony model'))
  it('posts to the configured API', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ recommendations: [recommendation] }))
    vi.stubGlobal('fetch', fetchMock)
    await new ApiRecommendationEngine('/ml', 'embedding-v2').recommend(request)
    expect(fetchMock).toHaveBeenCalledWith('/ml/recommend', expect.objectContaining({ method: 'POST' }))
  })
  it('serializes the generic request contract', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ recommendations: [] }))
    vi.stubGlobal('fetch', fetchMock)
    await new ApiRecommendationEngine('/ml', 'embedding-v2').recommend(request)
    const options = fetchMock.mock.calls[0][1]
    expect(JSON.parse(options.body)).toEqual({
      palette_id: 'palette-x', engine_id: 'embedding-v2', colors: [
        { id: 'red', name: 'Red', hex: '#ff0000', rgb: [255, 0, 0] },
        { id: 'custom:#123456', name: 'Custom color', hex: '#123456', rgb: [18, 52, 86] },
      ], mode: 'vivid', scope: 'spectrum', limit: 6,
    })
  })
  it('sends JSON content headers', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ recommendations: [] }))
    vi.stubGlobal('fetch', fetchMock)
    await new ApiRecommendationEngine().recommend(request)
    expect(fetchMock.mock.calls[0][1].headers).toEqual({ 'Content-Type': 'application/json' })
  })
  it('returns normalized remote recommendations unchanged', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ recommendations: [recommendation] })))
    expect(await new ApiRecommendationEngine().recommend(request)).toEqual([recommendation])
  })
  it('supports an empty recommendation response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ recommendations: [] })))
    expect(await new ApiRecommendationEngine().recommend(request)).toEqual([])
  })
  it('throws a useful HTTP error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({}, false, 422)))
    await expect(new ApiRecommendationEngine().recommend(request)).rejects.toThrow('Recommendation service failed (422)')
  })
  it('propagates network failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('connection lost')))
    await expect(new ApiRecommendationEngine().recommend(request)).rejects.toThrow('connection lost')
  })

  it('requests a palette-level assessment without mode or result scope', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ assessment }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(new ApiRecommendationEngine('/ml', 'embedding-v2').assess({ dataset: request.dataset, selectedColors: request.selectedColors })).resolves.toEqual(assessment)
    expect(fetchMock).toHaveBeenCalledWith('/ml/assess', expect.objectContaining({ method: 'POST' }))
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      palette_id: 'palette-x', engine_id: 'embedding-v2', colors: [
        { id: 'red', name: 'Red', hex: '#ff0000', rgb: [255, 0, 0] },
        { id: 'custom:#123456', name: 'Custom color', hex: '#123456', rgb: [18, 52, 86] },
      ],
    })
  })

  it('supports unavailable and failed palette assessments', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ assessment: null })))
    await expect(new ApiRecommendationEngine().assess({ dataset: request.dataset, selectedColors: request.selectedColors })).resolves.toBeNull()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({}, false, 503)))
    await expect(new ApiRecommendationEngine().assess({ dataset: request.dataset, selectedColors: request.selectedColors })).rejects.toThrow('Palette assessment failed (503)')
  })
})
