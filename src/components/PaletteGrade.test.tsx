import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { PaletteGrade } from './PaletteGrade'

const assessment = {
  grade: 'B', score: 76, label: 'Strong Wada affinity',
  summary: "This palette is well supported by Wada's archive.",
  details: ["1 of 1 selected color pairs appear together in Wada's combinations.", '84% ensemble structure fit.'],
}

describe('PaletteGrade', () => {
  it('renders the grade, score, label, and evidence', () => {
    const html = renderToStaticMarkup(<PaletteGrade assessment={assessment} status="ready" selectedCount={2} />)
    expect(html).toContain('Wada palette grade')
    expect(html).toContain('B')
    expect(html).toContain('76 / 100')
    expect(html).toContain('Strong Wada affinity')
    expect(html).toContain('1 of 1 selected color pairs')
  })

  it('asks for a second color before grading', () => {
    const html = renderToStaticMarkup(<PaletteGrade assessment={null} status="idle" selectedCount={1} />)
    expect(html).toContain('Add another color')
    expect(html).toContain('at least two colors')
  })

  it('renders loading and recoverable error states', () => {
    expect(renderToStaticMarkup(<PaletteGrade assessment={null} status="loading" selectedCount={2} />)).toContain('Comparing with Wada')
    expect(renderToStaticMarkup(<PaletteGrade assessment={null} status="error" selectedCount={2} />)).toContain('Grade unavailable')
  })
})
