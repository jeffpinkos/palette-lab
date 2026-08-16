import { afterEach, describe, expect, it, vi } from 'vitest'
import { WadaPaletteProvider } from './wadaPaletteProvider'

const payload = { colors: [
  { index: 7, name: 'First', hex: '#112233', rgb_array: [17, 34, 51], combinations: [2, 8], use_count: 2 },
  { index: 9, name: 'Second', hex: '#abcdef', rgb_array: [171, 205, 239], combinations: [], use_count: 0 },
] }

const response = (body = payload, ok = true, status = 200) => ({ ok, status, json: vi.fn().mockResolvedValue(body) })

afterEach(() => vi.unstubAllGlobals())

describe('WadaPaletteProvider', () => {
  it('has a stable palette ID', () => expect(new WadaPaletteProvider().id).toBe('wada-1933'))
  it('loads from the default URL', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response())
    vi.stubGlobal('fetch', fetchMock)
    await new WadaPaletteProvider().load()
    expect(fetchMock).toHaveBeenCalledWith('/colors.json')
  })
  it('supports a custom source URL', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response())
    vi.stubGlobal('fetch', fetchMock)
    await new WadaPaletteProvider('/fixtures/wada.json').load()
    expect(fetchMock).toHaveBeenCalledWith('/fixtures/wada.json')
  })
  it('normalizes source-specific color fields', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response()))
    const dataset = await new WadaPaletteProvider().load()
    expect(dataset.colors[0]).toEqual({
      id: '7', name: 'First', hex: '#112233', rgb: [17, 34, 51], metadata: { sourceIndex: 7, useCount: 2 },
    })
  })
  it('repairs obvious source casing mistakes for display', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ colors: [{ ...payload.colors[0], name: 'Calamine BLue' }] })))
    expect((await new WadaPaletteProvider().load()).colors[0].name).toBe('Calamine Blue')
  })
  it('normalizes numeric group IDs to strings', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response()))
    expect((await new WadaPaletteProvider().load()).groupsByColor).toEqual({ '7': ['2', '8'], '9': [] })
  })
  it('supplies Wada metadata only at the adapter boundary', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response()))
    const metadata = (await new WadaPaletteProvider().load()).metadata
    expect(metadata).toMatchObject({ id: 'wada-1933', name: 'WADA', sourceName: 'Sanzo Wada', groupLabel: 'historic combinations' })
  })
  it('supplies default selection IDs', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response()))
    expect((await new WadaPaletteProvider().load()).defaultColorIds).toEqual(['19', '112'])
  })
  it('declares the known group count independently of a small fixture', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response()))
    expect((await new WadaPaletteProvider().load()).groupCount).toBe(348)
  })
  it('preserves an empty palette', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ colors: [] })))
    expect((await new WadaPaletteProvider().load()).colors).toEqual([])
  })
  it('throws a useful HTTP error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(payload, false, 503)))
    await expect(new WadaPaletteProvider().load()).rejects.toThrow('Unable to load Wada palette (503)')
  })
  it('propagates network errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    await expect(new WadaPaletteProvider().load()).rejects.toThrow('offline')
  })
})
