import { runtime } from '@/config'
import { LabFooter, LabHeader, MethodSection, PaletteComposer, RecommendationPanel } from '@/features/palette-lab'
import { usePaletteLab } from '@/hooks'

export default function App() {
  const lab = usePaletteLab(runtime)
  const palette = lab.dataset

  if (!palette) return <main className="loading-state"><p>{lab.error ?? 'Loading palette…'}</p></main>

  return <main id="top">
    <LabHeader metadata={palette.metadata} groupCount={palette.groupCount} />
    <div id="lab" className="workspace">
      <PaletteComposer
        palette={palette}
        selected={lab.selected}
        maxSelections={runtime.maxSelections}
        colorNameCount={runtime.colorNamer.count}
        isNaming={lab.isNaming}
        assessment={lab.assessment}
        assessmentStatus={lab.assessmentStatus}
        status={lab.status}
        mode={lab.mode}
        scope={lab.scope}
        searchColorNames={lab.searchColorNames}
        onAdd={lab.addColor}
        onRemove={lab.removeColor}
        onGenerate={() => void lab.generate()}
        onExploreWada={() => { lab.setScope('palette'); void lab.generate(lab.mode, 'palette') }}
        onModeChange={lab.setMode}
        onScopeChange={lab.setScope}
      />
      <RecommendationPanel results={lab.results} status={lab.status} error={lab.error} onAdd={lab.addColor} />
    </div>
    <MethodSection metadata={palette.metadata} selected={lab.selected} results={lab.results} />
    <LabFooter metadata={palette.metadata} colorCount={palette.colors.length} groupCount={palette.groupCount} colorNameCount={runtime.colorNamer.count} />
  </main>
}
