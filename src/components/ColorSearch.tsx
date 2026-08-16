import { useMemo, useState } from 'react'
import { Plus, Search, X } from 'lucide-react'
import { closestColor } from '../lib/colorMath'
import type { ColorId, PaletteColor } from '../domain/palette'

type Props = {
  colors: PaletteColor[]
  selected: PaletteColor[]
  paletteName: string
  maxSelections: number
  onAdd: (color: PaletteColor) => void
  onRemove: (id: ColorId) => void
}

export function ColorSearch({ colors, selected, paletteName, maxSelections, onAdd, onRemove }: Props) {
  const [query, setQuery] = useState('')
  const [hex, setHex] = useState('#d95040')
  const matches = useMemo(() => query.trim() ? colors.filter((color) => `${color.name} ${color.hex}`.toLowerCase().includes(query.toLowerCase())).slice(0, 6) : [], [colors, query])

  const addHex = () => {
    const color = closestColor(colors, hex)
    if (color) onAdd(color)
  }

  return <div className="selection-panel">
    <div className="search-wrap">
      <Search size={17} aria-hidden="true" />
      <input aria-label={`Search ${paletteName} colors`} value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${colors.length} ${paletteName} colors`} />
      {matches.length > 0 ? <div className="search-results">{matches.map((color) => <button key={color.id} onClick={() => { onAdd(color); setQuery('') }}><span style={{ background: color.hex }} />{color.name}<small>{color.hex}</small></button>)}</div> : null}
    </div>
    <div className="hex-row">
      <label><span style={{ background: /^#[0-9a-f]{6}$/i.test(hex) ? hex : '#d95040' }} /><input aria-label="Hex color" value={hex} onChange={(event) => setHex(event.target.value)} /></label>
      <button className="secondary" onClick={addHex}><Plus size={17} />Add color</button>
    </div>
    <p className="count">{selected.length} / {maxSelections} colors selected</p>
    <div className="selected-colors">
      {selected.map((color, index) => <article key={color.id} className="selected-swatch">
        <div className="color-field" style={{ background: color.hex }}><span>{String(index + 1).padStart(2, '0')}</span></div>
        <footer><div><strong>{color.name}</strong><small>{color.hex}</small></div><button aria-label={`Remove ${color.name}`} onClick={() => onRemove(color.id)}><X size={16} /></button></footer>
      </article>)}
      {Array.from({ length: Math.max(0, Math.min(3, maxSelections) - selected.length) }).map((_, index) => <div className="empty-swatch" key={index}>+</div>)}
    </div>
  </div>
}
