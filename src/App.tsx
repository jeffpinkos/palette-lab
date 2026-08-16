import { ArrowRight, CircleHelp } from 'lucide-react'
import { ColorSearch } from './components/ColorSearch'
import { Results } from './components/Results'
import { runtime } from './config/runtime'
import { usePaletteLab } from './hooks/usePaletteLab'
import type { HarmonyMode } from './domain/palette'

const MODES: HarmonyMode[] = ['quiet', 'balanced', 'vivid']

export default function App() {
  const lab = usePaletteLab(runtime)
  const palette = lab.dataset
  if (!palette) return <main className="loading-state"><p>{lab.error ?? 'Loading palette…'}</p></main>
  const { metadata } = palette

  return <main>
    <header className="site-header"><a className="brand" href="#top">{metadata.name}</a><nav><a className="active" href="#lab">Palette laboratory</a><a href="#method">About the method</a></nav><div className="edition"><span>◉</span><b>{metadata.editionLabel ?? palette.groupCount}</b></div></header>
    <div id="lab" className="workspace">
      <section className="composer">
        <div className="intro"><h1>Find colors that<br />belong together.</h1><p>{metadata.description}</p></div>
        <ColorSearch colors={palette.colors} selected={lab.selected} paletteName={metadata.name} maxSelections={runtime.maxSelections} onAdd={lab.addColor} onRemove={lab.removeColor} />
        <button className="primary" disabled={!lab.selected.length || lab.status === 'recommending'} onClick={() => void lab.generate()}>{lab.status === 'recommending' ? 'Finding harmonies…' : 'Find harmonies'} <ArrowRight size={19} /></button>
        <fieldset className="modes"><legend>Mode</legend>{MODES.map((item) => <button key={item} className={lab.mode === item ? 'selected' : ''} onClick={() => lab.setMode(item)}>{item}<i /></button>)}</fieldset>
      </section>
      {lab.results.length > 0 ? <Results results={lab.results} /> : <section className="results empty-results"><div className="results-title"><h2>Suggested companions</h2><span>{lab.error ? 'Error' : 'Waiting'}</span></div><div className="empty-message"><div className="registration">＋</div><p>{lab.error ?? 'Your companion colors will appear here.'}</p><small>Select colors, then find their harmonies.</small></div></section>}
    </div>
    <section id="method" className="method"><div><h2>Why these colors?</h2><p>The active engine uses the training signals supplied by this palette. The current baseline scores normalized group co-occurrence, then tunes the result to your chosen mood.</p>{metadata.sourceUrl ? <a href={metadata.sourceUrl} target="_blank" rel="noreferrer">Explore {metadata.sourceName} <ArrowRight size={15} /></a> : null}</div><div className="method-visual"><div className="mini selected-mini">{lab.selected.slice(0, 3).map((color) => <i key={color.id} style={{ background: color.hex }} />)}</div><b>+</b><div className="mini">{lab.results.slice(0, 4).map((result) => <i key={result.color.id} style={{ background: result.color.hex }} />)}</div></div><aside><CircleHelp size={18} /><p>Affinity is produced by {runtime.recommendationEngine.name}. It is a recommendation score, not a probability.</p></aside></section>
    <footer className="footer"><span className="mark">⊕</span><span>Based on <b>{palette.colors.length}</b> colors and <b>{palette.groupCount}</b> {metadata.groupLabel}</span><span>{metadata.attribution}</span></footer>
  </main>
}
