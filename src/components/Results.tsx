import { Copy, Download, Plus } from 'lucide-react'
import { useState } from 'react'
import type { PaletteColor, Recommendation } from '@/domain'

export const fitLabel = (score: number) => score >= 0.62 ? 'Strong companion fit' : score >= 0.48 ? 'Good companion fit' : 'Exploratory companion'
export const cssPalette = (results: Recommendation[]) => `:root {\n${results.map((result, index) => `  --palette-${index + 1}: ${result.color.hex};`).join('\n')}\n}`
export const evidenceSummary = (result: Recommendation) => {
  if (!result.evidence) return ''
  const { label, value } = result.evidence
  return result.color.metadata?.generated && label.startsWith('related Wada group')
    ? `Projected through ${value} ${label}`
    : `${value} ${label}`
}

export function Results({ results, onAdd }: { results: Recommendation[]; onAdd: (color: PaletteColor) => void }) {
  const [copied, setCopied] = useState<string | null>(null)

  const copy = async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(label)
    } catch {
      setCopied('Copy unavailable')
    }
  }

  const download = () => {
    const url = URL.createObjectURL(new Blob([cssPalette(results)], { type: 'text/css' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'wada-palette.css'
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return <section className="results" aria-live="polite">
    <div className="results-title"><div><h2>Suggested companions</h2><span>{String(results.length).padStart(2, '0')} colors</span></div><div className="palette-actions"><button onClick={() => void copy(cssPalette(results), 'Palette copied')}><Copy size={14} />Copy CSS</button><button onClick={download}><Download size={14} />Export</button></div></div>
    {copied ? <p className="copy-status" role="status">{copied}</p> : null}
    <div className="result-rail">
      {results.map((result, index) => <article className="result" key={result.color.id} style={{ animationDelay: `${index * 70}ms` }}>
        <div className="result-color" style={{ background: result.color.hex }}><span>{String(index + 1).padStart(2, '0')}</span>{result.color.metadata?.generated ? <b>Generated</b> : null}</div>
        <h3 title={result.color.name}>{result.color.name}</h3><p>{result.color.hex}</p><strong className="fit-label">{fitLabel(result.score)}</strong>
        {result.evidence ? <div className="evidence"><b>{evidenceSummary(result)}</b>{result.evidence.details?.length ? <details><summary>Why this works</summary>{result.evidence.details.slice(0, 3).map((detail) => <span key={detail}>{detail}</span>)}</details> : null}</div> : null}
        <div className="result-actions"><button aria-label={`Add ${result.color.name} to selection`} onClick={() => onAdd(result.color)}><Plus size={14} />Add</button><button aria-label={`Copy ${result.color.hex}`} onClick={() => void copy(result.color.hex, `${result.color.hex} copied`)}><Copy size={14} />Hex</button></div>
      </article>)}
    </div>
  </section>
}
