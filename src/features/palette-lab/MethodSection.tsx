import { ArrowRight, CircleHelp } from 'lucide-react'
import type { PaletteColor, PaletteMetadata, Recommendation } from '@/domain'

type Props = {
  metadata: PaletteMetadata
  selected: PaletteColor[]
  results: Recommendation[]
}

export function MethodSection({ metadata, selected, results }: Props) {
  return <section id="method" className="method">
    <div><h2>Why these colors?</h2><p>The harmony model learns which colors Wada placed together, validates candidates against held-out combinations, and works in perceptual OKLab color space. It then chooses companions as a group, avoiding near-duplicates.</p>{metadata.sourceUrl ? <a href={metadata.sourceUrl} target="_blank" rel="noreferrer">Explore {metadata.sourceName} <ArrowRight size={15} /></a> : null}</div>
    <div className="method-visual"><div className="mini selected-mini">{selected.slice(0, 3).map((color) => <i key={color.id} style={{ background: color.hex }} />)}</div><b>+</b><div className="mini">{results.slice(0, 4).map((result) => <i key={result.color.id} style={{ background: result.color.hex }} />)}</div></div>
    <aside><CircleHelp size={18} /><p>The palette grade measures the selected colors' historical and modeled Wada affinity, not artistic quality. Companion fit measures how well each suggestion extends that selection.</p></aside>
  </section>
}
