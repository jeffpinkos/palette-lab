import { ArrowRight, CircleHelp } from 'lucide-react'
import { ColorSearch } from './components/ColorSearch'
import { PaletteGrade } from './components/PaletteGrade'
import { Results } from './components/Results'
import { runtime } from './config/runtime'
import { usePaletteLab } from './hooks/usePaletteLab'
import type { HarmonyMode, RecommendationScope } from './domain/palette'

const MODES: HarmonyMode[] = ['quiet', 'balanced', 'vivid']
const MODE_COPY: Record<HarmonyMode, string> = {
  quiet: 'Neighboring hues, restrained chroma, and gentle value shifts.',
  balanced: 'Measured hue intervals with useful light–dark contrast.',
  vivid: 'Higher chroma, wider hue intervals, and stronger contrast.',
}
const SCOPES: { value: RecommendationScope; label: string }[] = [
  { value: 'palette', label: 'Wada archive' },
  { value: 'spectrum', label: 'Full spectrum' },
]

export default function App() {
  const lab = usePaletteLab(runtime)
  const palette = lab.dataset
  if (!palette) return <main className="loading-state"><p>{lab.error ?? 'Loading palette…'}</p></main>
  const { metadata } = palette

  return <main id="top">
    <header className="site-header">
      <a className="brand" href="#top">{metadata.name}</a>
      <nav><a className="active" href="#lab">Palette laboratory</a><a href="#method">About the method</a></nav>
      <div className="edition"><span>◉</span><b>{metadata.editionLabel ?? `${palette.groupCount} combinations`}</b></div>
    </header>
    <div id="lab" className="workspace">
      <section className="composer">
        <div className="intro"><h1>Find colors that<br />belong together.</h1><p>{metadata.description}</p></div>
        <ColorSearch colors={palette.colors} selected={lab.selected} maxSelections={runtime.maxSelections} colorNameCount={runtime.colorNamer.count} isNaming={lab.isNaming} searchColorNames={lab.searchColorNames} onAdd={lab.addColor} onRemove={lab.removeColor} />
        <PaletteGrade assessment={lab.assessment} status={lab.assessmentStatus} selectedCount={lab.selected.length} />
        <button className="primary" disabled={!lab.selected.length || lab.status === 'recommending' || lab.isNaming} onClick={() => void lab.generate()}>{lab.isNaming ? 'Naming color…' : lab.status === 'recommending' ? 'Finding harmonies…' : 'Find harmonies'} <ArrowRight size={19} /></button>
        <fieldset className="modes"><legend>Creative direction</legend>{MODES.map((item) => <button key={item} aria-pressed={lab.mode === item} className={lab.mode === item ? 'selected' : ''} onClick={() => lab.setMode(item)}>{item}<i /></button>)}</fieldset>
        <p className="mode-note">{MODE_COPY[lab.mode]}</p>
        <fieldset className="scopes"><legend>Result source</legend>{SCOPES.map((item) => <button key={item.value} aria-pressed={lab.scope === item.value} className={lab.scope === item.value ? 'selected' : ''} onClick={() => lab.setScope(item.value)}>{item.label}</button>)}</fieldset>
      </section>
      {lab.results.length > 0
        ? <Results results={lab.results} onAdd={lab.addColor} />
        : <section className="results empty-results"><div className="results-title"><div><h2>Suggested companions</h2><span>{lab.error ? 'Error' : lab.status === 'recommending' ? 'Working' : 'Waiting'}</span></div></div><div className="empty-message"><div className="registration">＋</div><p>{lab.error ?? (lab.status === 'recommending' ? 'Building a varied palette…' : 'Your companion colors will appear here.')}</p><small>{lab.error ? 'Check that the harmony service is running, then try again.' : 'Select colors, choose a direction, then find their harmonies.'}</small></div></section>}
    </div>
    <section id="method" className="method">
      <div><h2>Why these colors?</h2><p>The harmony model learns which colors Wada placed together, validates candidates against held-out combinations, and works in perceptual OKLab color space. It then chooses companions as a group, avoiding near-duplicates.</p>{metadata.sourceUrl ? <a href={metadata.sourceUrl} target="_blank" rel="noreferrer">Explore {metadata.sourceName} <ArrowRight size={15} /></a> : null}</div>
      <div className="method-visual"><div className="mini selected-mini">{lab.selected.slice(0, 3).map((color) => <i key={color.id} style={{ background: color.hex }} />)}</div><b>+</b><div className="mini">{lab.results.slice(0, 4).map((result) => <i key={result.color.id} style={{ background: result.color.hex }} />)}</div></div>
      <aside><CircleHelp size={18} /><p>The palette grade measures historical and modeled Wada affinity, not artistic quality. Each suggestion then explains its own hue interval, historic overlap, and custom-color anchors.</p></aside>
    </section>
    <footer className="footer"><span className="mark">⊕</span><span>Based on <b>{palette.colors.length}</b> colors and <b>{palette.groupCount}</b> {metadata.groupLabel}</span><span>{runtime.colorNamer.count.toLocaleString()} Color Name List names · {metadata.attribution}</span></footer>
  </main>
}
