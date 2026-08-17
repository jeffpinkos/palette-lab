import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { PaletteColor } from '@/domain'
import { ColorSearch } from './ColorSearch'

const colors: PaletteColor[] = [
  { id: 'a', name: 'Archive red', hex: '#cc2233', rgb: [204, 34, 51] },
  { id: 'b', name: 'Archive blue', hex: '#2244cc', rgb: [34, 68, 204] },
  { id: 'c', name: 'Archive green', hex: '#33aa55', rgb: [51, 170, 85] },
  { id: 'd', name: 'Archive gold', hex: '#ddaa22', rgb: [221, 170, 34] },
]

const render = (selected: PaletteColor[] = [], isNaming = false) => renderToStaticMarkup(<ColorSearch colors={colors} selected={selected} maxSelections={4} colorNameCount={31_914} isNaming={isNaming} searchColorNames={vi.fn().mockResolvedValue([])} onAdd={vi.fn()} onRemove={vi.fn()} />)

describe('ColorSearch', () => {
  it('describes arbitrary hex support before an error occurs', () => {
    expect(render()).toContain('The closest of 31,914 names is applied automatically.')
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
  it('renders a slot for every permitted selection', () => {
    const html = render()
    expect((html.match(/class="empty-swatch"/g) ?? [])).toHaveLength(4)
  })
  it('advertises the complete searchable color-name catalog', () => {
    expect(render()).toContain('Search 31,914 color names')
    expect(render()).toContain('Search colors by name or hex')
  })
  it('shows when an arbitrary color is being named', () => {
    expect(render([], true)).toContain('Naming color…')
  })
})
