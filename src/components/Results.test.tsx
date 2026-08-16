import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { Recommendation } from '../domain/palette'
import { cssPalette, fitLabel, Results } from './Results'

const results: Recommendation[] = [
  {
    color: { id: 'generated:#123456', name: 'Spectrum Azure', hex: '#123456', rgb: [18, 52, 86], metadata: { generated: true } },
    score: .72,
    evidence: { label: 'shared Wada groups', value: 3, details: ['triadic interval · 120° · ΔL 24', 'Generated in perceptual OKLCH space'] },
  },
  { color: { id: 'archive', name: 'Archive green', hex: '#abcdef', rgb: [171, 205, 239] }, score: .41 },
]

describe('Results', () => {
  it('renders generated provenance and artist-facing evidence', () => {
    const html = renderToStaticMarkup(<Results results={results} onAdd={vi.fn()} />)
    expect(html).toContain('Generated')
    expect(html).toContain('3 shared Wada groups')
    expect(html).toContain('triadic interval')
    expect(html).toContain('Strong fit')
  })
  it('exposes add, copy, and export actions', () => {
    const html = renderToStaticMarkup(<Results results={results} onAdd={vi.fn()} />)
    expect(html).toContain('Add Spectrum Azure to selection')
    expect(html).toContain('Copy #123456')
    expect(html).toContain('Copy CSS')
    expect(html).toContain('Export')
  })
})

describe('fitLabel', () => {
  it.each([[.8, 'Strong fit'], [.62, 'Strong fit'], [.61, 'Good fit'], [.48, 'Good fit'], [.47, 'Exploratory']] as const)('maps %s to %s', (score, label) => {
    expect(fitLabel(score)).toBe(label)
  })
})

describe('cssPalette', () => {
  it('exports stable numbered CSS variables', () => {
    expect(cssPalette(results)).toBe(':root {\n  --palette-1: #123456;\n  --palette-2: #abcdef;\n}')
  })
})
