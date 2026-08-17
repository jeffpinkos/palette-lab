import { ArrowRight } from 'lucide-react'
import { ColorSearch, PaletteGrade } from '@/components'
import type { ColorId, HarmonyMode, PaletteAssessment, PaletteColor, PaletteDataset, RecommendationScope } from '@/domain'
import { HARMONY_MODES, MODE_COPY, RECOMMENDATION_SCOPES } from './options'

type Props = {
  palette: PaletteDataset
  selected: PaletteColor[]
  maxSelections: number
  colorNameCount: number
  isNaming: boolean
  assessment: PaletteAssessment | null
  assessmentStatus: 'idle' | 'loading' | 'ready' | 'error'
  status: 'loading' | 'ready' | 'recommending' | 'error'
  mode: HarmonyMode
  scope: RecommendationScope
  searchColorNames: (query: string, limit?: number) => Promise<PaletteColor[]>
  onAdd: (color: PaletteColor) => void | Promise<void>
  onRemove: (id: ColorId) => void
  onGenerate: () => void
  onExploreWada: () => void
  onModeChange: (mode: HarmonyMode) => void
  onScopeChange: (scope: RecommendationScope) => void
}

export function PaletteComposer({
  palette, selected, maxSelections, colorNameCount, isNaming, assessment, assessmentStatus, status, mode, scope,
  searchColorNames, onAdd, onRemove, onGenerate, onExploreWada, onModeChange, onScopeChange,
}: Props) {
  const actionLabel = isNaming ? 'Naming color…' : status === 'recommending' ? 'Finding harmonies…' : 'Find harmonies'

  return <section className="composer">
    <div className="intro"><h1>Find colors that<br />belong together.</h1><p>{palette.metadata.description}</p></div>
    <ColorSearch colors={palette.colors} selected={selected} maxSelections={maxSelections} colorNameCount={colorNameCount} isNaming={isNaming} searchColorNames={searchColorNames} onAdd={onAdd} onRemove={onRemove} />
    <PaletteGrade assessment={assessment} status={assessmentStatus} selectedCount={selected.length} onExplore={onExploreWada} />
    <button className="primary" disabled={!selected.length || status === 'recommending' || isNaming} onClick={onGenerate}>{actionLabel} <ArrowRight size={19} /></button>
    <fieldset className="modes"><legend>Creative direction</legend>{HARMONY_MODES.map((item) => <button key={item} aria-pressed={mode === item} className={mode === item ? 'selected' : ''} onClick={() => onModeChange(item)}>{item}<i /></button>)}</fieldset>
    <p className="mode-note">{MODE_COPY[mode]}</p>
    <fieldset className="scopes"><legend>Result source</legend>{RECOMMENDATION_SCOPES.map((item) => <button key={item.value} aria-pressed={scope === item.value} className={scope === item.value ? 'selected' : ''} onClick={() => onScopeChange(item.value)}>{item.label}</button>)}</fieldset>
  </section>
}
