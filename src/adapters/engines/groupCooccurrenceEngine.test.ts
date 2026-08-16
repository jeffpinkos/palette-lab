import { describe, expect, it } from 'vitest'
import { GroupCooccurrenceEngine } from './groupCooccurrenceEngine'
import type { PaletteDataset } from '../../domain/palette'

const dataset: PaletteDataset = {
  metadata: { id: 'sample', name: 'Sample', description: '', sourceName: 'Test', groupLabel: 'sets' },
  colors: [
    { id: 'a', name: 'Red', hex: '#ff0000', rgb: [255, 0, 0] },
    { id: 'b', name: 'Blue', hex: '#0000ff', rgb: [0, 0, 255] },
    { id: 'c', name: 'Near red', hex: '#ee1010', rgb: [238, 16, 16] },
    { id: 'd', name: 'Green', hex: '#00ff00', rgb: [0, 255, 0] },
    { id: 'e', name: 'Orphan', hex: '#ffffff', rgb: [255, 255, 255] },
  ],
  groupsByColor: { a: ['one', 'two'], b: ['one', 'two'], c: ['one'], d: ['two'], e: [] },
  groupCount: 3,
}

const recommend = (overrides: Partial<Parameters<GroupCooccurrenceEngine['recommend']>[0]> = {}) => new GroupCooccurrenceEngine().recommend({
  dataset, selectedColors: [dataset.colors[0]], mode: 'balanced', limit: 4, ...overrides,
})

describe('GroupCooccurrenceEngine', () => {
  it('publishes a stable identity', () => {
    const engine = new GroupCooccurrenceEngine()
    expect(engine.id).toBe('group-cooccurrence-v1')
    expect(engine.name).toBe('Group co-occurrence')
  })
  it('uses only the generic palette contract', async () => {
    expect((await recommend()).map((item) => item.color.id)).toEqual(['b', 'd', 'c'])
  })
  it('returns no results without selections', async () => expect(await recommend({ selectedColors: [] })).toEqual([]))
  it('projects an arbitrary color onto the nearest palette anchor', async () => {
    const custom = { id: 'custom:#fd0101', name: 'Custom color', hex: '#fd0101', rgb: [253, 1, 1] as [number, number, number] }
    expect(await recommend({ selectedColors: [custom] })).toHaveLength(3)
  })
  it('returns no results for an empty palette', async () => {
    expect(await recommend({ dataset: { ...dataset, colors: [] }, selectedColors: [{ id: 'x', name: 'X', hex: '#000000', rgb: [0, 0, 0] }] })).toEqual([])
  })
  it('excludes selected colors', async () => {
    expect((await recommend({ selectedColors: [dataset.colors[0], dataset.colors[1]] })).map((item) => item.color.id)).not.toContain('a')
  })
  it('excludes candidates with no group overlap', async () => {
    expect((await recommend()).map((item) => item.color.id)).not.toContain('e')
  })
  it('respects a zero result limit', async () => expect(await recommend({ limit: 0 })).toEqual([]))
  it('respects a smaller result limit', async () => expect(await recommend({ limit: 2 })).toHaveLength(2))
  it('returns all available results when the limit is large', async () => expect(await recommend({ limit: 99 })).toHaveLength(3))
  it('returns normalized finite scores', async () => {
    for (const item of await recommend()) {
      expect(Number.isFinite(item.score)).toBe(true)
      expect(item.score).toBeGreaterThan(0)
      expect(item.score).toBeLessThanOrEqual(1)
    }
  })
  it('attaches explainable evidence', async () => {
    expect((await recommend())[0].evidence).toEqual({ label: 'shared', value: 2 })
  })
  it('favors perceptually near candidates in quiet mode', async () => {
    const ids = (await recommend({ mode: 'quiet' })).map((item) => item.color.id)
    expect(ids.indexOf('c')).toBeLessThan(ids.indexOf('d'))
  })
  it('favors perceptually distant candidates in vivid mode', async () => {
    const ids = (await recommend({ mode: 'vivid' })).map((item) => item.color.id)
    expect(ids.indexOf('d')).toBeLessThan(ids.indexOf('c'))
  })
  it('does not mutate colors, groups, or selections', async () => {
    const before = JSON.stringify(dataset)
    const selected = [dataset.colors[0]]
    await recommend({ selectedColors: selected })
    expect(JSON.stringify(dataset)).toBe(before)
    expect(selected).toEqual([dataset.colors[0]])
  })
  it('supports palettes whose colors omit groups', async () => {
    const sparse = { ...dataset, groupsByColor: { a: ['one'], b: ['one'] } }
    expect((await recommend({ dataset: sparse })).map((item) => item.color.id)).toEqual(['b'])
  })
  it('combines groups from multiple selected colors', async () => {
    const ids = (await recommend({ selectedColors: [dataset.colors[2], dataset.colors[3]] })).map((item) => item.color.id)
    expect(ids).toContain('a')
    expect(ids).toContain('b')
  })
  it('does not recommend the palette anchor used for a custom color', async () => {
    const custom = { id: 'custom:#fe0101', name: 'Custom color', hex: '#fe0101', rgb: [254, 1, 1] as [number, number, number] }
    expect((await recommend({ selectedColors: [custom] })).map((item) => item.color.id)).not.toContain('a')
  })
  it('uses the exact custom RGB value for mood distance', async () => {
    const custom = { id: 'custom:#fe0101', name: 'Custom color', hex: '#fe0101', rgb: [254, 1, 1] as [number, number, number] }
    const quiet = await recommend({ selectedColors: [custom], mode: 'quiet' })
    expect(quiet.find((item) => item.color.id === 'c')!.score).toBeGreaterThan(quiet.find((item) => item.color.id === 'd')!.score)
  })
})
