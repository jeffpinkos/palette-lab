import type { PaletteAssessment } from '../domain/palette'

type Props = {
  assessment: PaletteAssessment | null
  status: 'idle' | 'loading' | 'ready' | 'error'
  selectedCount: number
}

export function PaletteGrade({ assessment, status, selectedCount }: Props) {
  const pending = selectedCount >= 2 && status === 'loading'
  const label = selectedCount < 2
    ? 'Add another color'
    : pending
      ? 'Comparing with Wada…'
      : status === 'error'
        ? 'Grade unavailable'
        : assessment?.label ?? 'Awaiting assessment'
  const summary = selectedCount < 2
    ? 'A palette needs at least two colors before its relationships can be graded.'
    : pending
      ? 'Checking historical combinations and learned relationship structure.'
      : status === 'error'
        ? 'The recommendations still work; retry after the assessment service reconnects.'
        : assessment?.summary ?? 'Select colors to measure their Wada affinity.'

  return <section className="palette-grade" aria-label="Wada palette grade" aria-live="polite">
    <div className="grade-mark"><span>Wada palette grade</span><strong>{assessment?.grade ?? '—'}</strong>{assessment?.score == null ? null : <small>{assessment.score} / 100</small>}</div>
    <div className="grade-copy"><b>{label}</b><p>{summary}</p>{assessment?.details?.slice(0, 2).map((detail) => <small key={detail}>{detail}</small>)}</div>
  </section>
}
