import { useCallback, useEffect, useRef, useState } from 'react'
import type { LabRuntime } from '../config/runtime'
import type { ColorId, HarmonyMode, PaletteColor, PaletteDataset, Recommendation, RecommendationScope } from '../domain/palette'

export function usePaletteLab(runtime: LabRuntime) {
  const [dataset, setDataset] = useState<PaletteDataset | null>(null)
  const [selected, setSelected] = useState<PaletteColor[]>([])
  const [mode, setModeState] = useState<HarmonyMode>('balanced')
  const [scope, setScopeState] = useState<RecommendationScope>('palette')
  const [results, setResults] = useState<Recommendation[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'recommending' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)
  const requestId = useRef(0)

  useEffect(() => {
    let active = true
    runtime.paletteProvider.load().then((loaded) => {
      if (!active) return
      setDataset(loaded)
      const colorsById = new Map(loaded.colors.map((color) => [color.id, color]))
      setSelected((loaded.defaultColorIds ?? []).flatMap((id) => { const color = colorsById.get(id); return color ? [color] : [] }).slice(0, runtime.maxSelections))
      setStatus('ready')
    }).catch((reason: unknown) => {
      if (!active) return
      setError(reason instanceof Error ? reason.message : 'Unable to load palette')
      setStatus('error')
    })
    return () => { active = false }
  }, [runtime])

  const generate = useCallback(async (nextMode = mode, nextScope = scope) => {
    if (!dataset || selected.length === 0) return
    const activeRequest = ++requestId.current
    setStatus('recommending')
    setError(null)
    setResults([])
    try {
      const nextResults = await runtime.recommendationEngine.recommend({ dataset, selectedColors: selected, mode: nextMode, scope: nextScope, limit: runtime.resultLimit })
      if (activeRequest !== requestId.current) return
      setResults(nextResults)
      setStatus('ready')
    } catch (reason) {
      if (activeRequest !== requestId.current) return
      setError(reason instanceof Error ? reason.message : 'Unable to generate recommendations')
      setStatus('error')
    }
  }, [dataset, mode, runtime, scope, selected])

  const invalidateResults = useCallback(() => {
    requestId.current += 1
    setResults([])
    setError(null)
    setStatus('ready')
  }, [])

  const addColor = useCallback((color: PaletteColor) => {
    if (selected.length >= runtime.maxSelections || selected.some((item) => item.id === color.id)) return
    setSelected([...selected, color])
    invalidateResults()
  }, [invalidateResults, runtime.maxSelections, selected])

  const removeColor = useCallback((id: ColorId) => {
    if (!selected.some((color) => color.id === id)) return
    setSelected(selected.filter((color) => color.id !== id))
    invalidateResults()
  }, [invalidateResults, selected])
  const setMode = useCallback((nextMode: HarmonyMode) => {
    setModeState(nextMode)
    if (results.length > 0) void generate(nextMode, scope)
  }, [generate, results.length, scope])
  const setScope = useCallback((nextScope: RecommendationScope) => {
    setScopeState(nextScope)
    if (results.length > 0) void generate(mode, nextScope)
  }, [generate, mode, results.length])

  return { dataset, selected, mode, scope, results, status, error, addColor, removeColor, setMode, setScope, generate }
}
