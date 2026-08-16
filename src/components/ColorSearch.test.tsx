import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { PaletteColor } from '../domain/palette'
import { ColorSearch } from './ColorSearch'

const colors: PaletteColor[] = [
  { id: 'a', name: 'Archive red', hex: '#cc2233', rgb: [204, 34, 51] },
  { id: 'b', name: 'Archive blue', hex: '#2244cc', rgb: [34, 68, 204] },
  { id: 'c', name: 'Archive green', hex: '#33aa55', rgb: [51, 170, 85] },
  { id: 'd', name: 'Archive gold', hex: '#ddaa22', rgb: [221, 170, 34] },
]

const render = (selected: PaletteColor[] = []) => renderToStaticMarkup(<ColorSearch colors={colors} selected={selected} paletteName="Archive" maxSelections={4} onAdd={vi.fn()} onRemove={vi.fn()} />)

describe('ColorSearch', () => {
  it('describes arbitrary hex support before an error occurs', () => {
    expect(render()).toContain('Use any six-digit hex color—not only colors in the archive.')
  })
  it('publishes combobox state for assistive technology', () => {
    expect(render()).toContain('role="combobox"')
    expect(render()).toContain('aria-expanded="false"')
  })
  it('disables additions when the selection limit is reached', () => {
    const html = render(colors)
    expect(html).toContain('4 / 4 colors selected')
    expect(html).toMatch(/<button class="secondary" disabled=""/)
  })
  it('renders removal controls with color-specific labels', () => {
    expect(render([colors[0]])).toContain('Remove Archive red')
  })
})
