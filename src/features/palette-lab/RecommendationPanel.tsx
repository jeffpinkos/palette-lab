import { Results } from '@/components'
import type { PaletteColor, Recommendation } from '@/domain'

type Props = {
  results: Recommendation[]
  status: 'loading' | 'ready' | 'recommending' | 'error'
  error: string | null
  onAdd: (color: PaletteColor) => void
}

export function RecommendationPanel({ results, status, error, onAdd }: Props) {
  if (results.length > 0) return <Results results={results} onAdd={onAdd} />
  const label = error ? 'Error' : status === 'recommending' ? 'Working' : 'Waiting'
  const message = error ?? (status === 'recommending' ? 'Building a varied palette…' : 'Your companion colors will appear here.')
  const help = error ? 'Check that the harmony service is running, then try again.' : 'Select colors, choose a direction, then find their harmonies.'

  return <section className="results empty-results">
    <div className="results-title"><div><h2>Suggested companions</h2><span>{label}</span></div></div>
    <div className="empty-message"><div className="registration">＋</div><p>{message}</p><small>{help}</small></div>
  </section>
}
