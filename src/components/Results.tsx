import type { Recommendation } from '../domain/palette'

export function Results({ results }: { results: Recommendation[] }) {
  return <section className="results" aria-live="polite">
    <div className="results-title"><h2>Suggested companions</h2><span>{String(results.length).padStart(2, '0')} colors</span></div>
    <div className="result-rail">
      {results.map((result, index) => <article className="result" key={result.color.id} style={{ animationDelay: `${index * 70}ms` }}>
        <div className="result-color" style={{ background: result.color.hex }}><span>{String(index + 1).padStart(2, '0')}</span></div>
        <h3>{result.color.name}</h3><p>{result.color.hex}</p><small>{Math.round(result.score * 100)}% affinity{result.evidence ? ` · ${result.evidence.value} ${result.evidence.label}` : ''}</small>
      </article>)}
    </div>
  </section>
}
