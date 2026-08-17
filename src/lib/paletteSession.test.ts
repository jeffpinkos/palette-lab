import { describe, expect, it, vi } from 'vitest'
import { paletteSessionFromCookie, parsePaletteSession, readPaletteSession, savePaletteSession } from './paletteSession'

const session = { colors: [{ id: '19', name: 'Etruscan Red', hex: '#c9303e', rgb: [201, 48, 62] as [number, number, number] }], mode: 'balanced' as const, scope: 'companions' as const }

describe('paletteSession', () => {
  it('round-trips a versioned palette session through a cookie', () => {
    const value = encodeURIComponent(JSON.stringify({ version: 1, ...session }))
    expect(paletteSessionFromCookie(`theme=paper; wada-last-palette=${value}`)).toEqual({ version: 1, ...session })
  })

  it('rejects malformed, incompatible, and invalid palette sessions', () => {
    expect(parsePaletteSession('%not-json')).toBeNull()
    expect(parsePaletteSession(encodeURIComponent(JSON.stringify({ version: 2, ...session })))).toBeNull()
    expect(parsePaletteSession(encodeURIComponent(JSON.stringify({ version: 1, ...session, scope: 'unknown' })))).toBeNull()
  })

  it('writes the last recorded palette with safe cookie attributes', () => {
    const documentStub = { cookie: '' }
    vi.stubGlobal('document', documentStub)
    savePaletteSession(session)
    expect(documentStub.cookie).toContain('wada-last-palette=')
    expect(documentStub.cookie).toContain('Max-Age=2592000; Path=/; SameSite=Lax')
    expect(readPaletteSession()).toEqual({ version: 1, ...session })
    vi.unstubAllGlobals()
  })
})
