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
  groupsByColor: { a: ['one', 'two'], b: ['one', 'two'], c: ['one'], d: ['two', 'three'], e: [] },
  groupCount: 3,
}

const recommend = (overrides: Partial<Parameters<GroupCooccurrenceEngine['recommend']>[0]> = {}) => new GroupCooccurrenceEngine().recommend({
  dataset, selectedColorIds: ['a'], mode: 'balanced', limit: 4, ...overrides,
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
  it('returns no results without selections', async () => expect(await recommend({ selectedColorIds: [] })).toEqual([]))
  it('ignores unknown selected IDs when a known ID remains', async () => {
    expect(await recommend({ selectedColorIds: ['unknown', 'a'] })).toHaveLength(3)
  })
  it('returns no results when every selected ID is unknown', async () => {
    expect(await recommend({ selectedColorIds: ['unknown'] })).toEqual([])
  })
  it('excludes selected colors', async () => {
    expect((await recommend({ selectedColorIds: ['a', 'b'] })).map((item) => item.color.id)).not.toContain('a')
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
    const selected = ['a']
    await recommend({ selectedColorIds: selected })
    expect(JSON.stringify(dataset)).toBe(before)
    expect(selected).toEqual(['a'])
  })
  it('supports palettes whose colors omit groups', async () => {
    const sparse = { ...dataset, groupsByColor: { a: ['one'], b: ['one'] } }
    expect((await recommend({ dataset: sparse })).map((item) => item.color.id)).toEqual(['b'])
  })
  it('combines groups from multiple selected colors', async () => {
    const ids = (await recommend({ selectedColorIds: ['c', 'd'] })).map((item) => item.color.id)
    expect(ids).toContain('a')
    expect(ids).toContain('b')
  })
})
