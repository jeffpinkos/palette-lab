import { useMemo, useState } from 'react'
import { Plus, Search, X } from 'lucide-react'
import { colorFromHex, normalizeHex } from '../lib/colorMath'
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
  const [hexTouched, setHexTouched] = useState(false)
  const normalizedHex = normalizeHex(hex)
  const atLimit = selected.length >= maxSelections
  const matches = useMemo(() => query.trim() ? colors.filter((color) => `${color.name} ${color.hex}`.toLowerCase().includes(query.toLowerCase())).slice(0, 6) : [], [colors, query])

  const addHex = () => {
    const color = colorFromHex(colors, hex)
    if (color) onAdd(color)
  }

  return <div className="selection-panel">
    <div className="search-wrap">
      <Search size={17} aria-hidden="true" />
      <input role="combobox" aria-expanded={matches.length > 0} aria-controls="palette-search-results" aria-label={`Search ${paletteName} colors`} value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${colors.length} ${paletteName} colors`} />
      {matches.length > 0 ? <ul id="palette-search-results" role="listbox" className="search-results">{matches.map((color) => <li key={color.id} role="option" aria-selected={selected.some((item) => item.id === color.id)}><button disabled={atLimit || selected.some((item) => item.id === color.id)} onClick={() => { onAdd(color); setQuery('') }}><span style={{ background: color.hex }} />{color.name}<small>{color.hex}</small></button></li>)}</ul> : null}
    </div>
    <div className="hex-row">
      <label className="hex-input"><input className="color-picker" type="color" aria-label="Pick any color" value={normalizedHex ?? '#d95040'} onChange={(event) => { setHex(event.target.value); setHexTouched(true) }} /><input className="hex-text" aria-label="Hex color" aria-invalid={hexTouched && !normalizedHex} aria-describedby="hex-help" value={hex} onChange={(event) => { setHex(event.target.value); setHexTouched(true) }} onBlur={() => setHexTouched(true)} onKeyDown={(event) => { if (event.key === 'Enter' && normalizedHex && !atLimit) addHex() }} /></label>
      <button className="secondary" disabled={!normalizedHex || atLimit} onClick={addHex}><Plus size={17} />Add any color</button>
    </div>
    <p id="hex-help" className={`field-help ${hexTouched && !normalizedHex ? 'error' : ''}`}>{hexTouched && !normalizedHex ? 'Enter a six-digit hex color, such as #C8FF00.' : 'Use any six-digit hex color—not only colors in the archive.'}</p>
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
