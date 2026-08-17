import { useCallback, useEffect, useRef, useState } from 'react'
import type { LabRuntime } from '@/config'
import type { ColorId, HarmonyMode, PaletteAssessment, PaletteColor, PaletteDataset, Recommendation, RecommendationScope } from '@/domain'
import { readPaletteSession, savePaletteSession } from '@/lib'

export function usePaletteLab(runtime: LabRuntime) {
  const [dataset, setDataset] = useState<PaletteDataset | null>(null)
  const [selected, setSelected] = useState<PaletteColor[]>([])
  const [mode, setModeState] = useState<HarmonyMode>('balanced')
  const [scope, setScopeState] = useState<RecommendationScope>('palette')
  const [results, setResults] = useState<Recommendation[]>([])
  const [assessment, setAssessment] = useState<PaletteAssessment | null>(null)
  const [assessmentStatus, setAssessmentStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const [namingCount, setNamingCount] = useState(0)
  const [status, setStatus] = useState<'loading' | 'ready' | 'recommending' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)
  const requestId = useRef(0)
  const assessmentRequestId = useRef(0)
  const assessmentCache = useRef(new Map<string, PaletteAssessment | null>())

  useEffect(() => {
    let active = true
    runtime.paletteProvider.load().then((loaded) => {
      if (!active) return
      setDataset(loaded)
      const colorsById = new Map(loaded.colors.map((color) => [color.id, color]))
      const saved = readPaletteSession()
      const restored = saved?.colors.flatMap((color) => {
        const archiveColor = colorsById.get(color.id)
        return archiveColor?.hex.toLowerCase() === color.hex.toLowerCase() ? [archiveColor] : [color]
      }).filter((color, index, colors) => colors.findIndex((item) => item.id === color.id || item.hex === color.hex) === index).slice(0, runtime.maxSelections)
      setSelected(restored?.length ? restored : (loaded.defaultColorIds ?? []).flatMap((id) => { const color = colorsById.get(id); return color ? [color] : [] }).slice(0, runtime.maxSelections))
      if (saved) {
        setModeState(saved.mode)
        setScopeState(saved.scope)
      }
      setStatus('ready')
    }).catch((reason: unknown) => {
      if (!active) return
      setError(reason instanceof Error ? reason.message : 'Unable to load palette')
      setStatus('error')
    })
    return () => { active = false }
  }, [runtime])

  useEffect(() => {
    const activeRequest = ++assessmentRequestId.current
    setAssessment(null)
    if (!dataset || selected.length < 2 || !runtime.recommendationEngine.assess) {
      setAssessmentStatus('idle')
      return
    }
    const cacheKey = selected.map((color) => `${color.id}:${color.hex}`).sort().join('|')
    const cached = assessmentCache.current.get(cacheKey)
    if (cached !== undefined) {
      setAssessment(cached)
      setAssessmentStatus('ready')
      return
    }
    setAssessmentStatus('loading')
    const timer = window.setTimeout(() => {
      void runtime.recommendationEngine.assess!({ dataset, selectedColors: selected }).then((nextAssessment) => {
        if (activeRequest !== assessmentRequestId.current) return
        assessmentCache.current.set(cacheKey, nextAssessment)
        setAssessment(nextAssessment)
        setAssessmentStatus('ready')
      }).catch(() => {
        if (activeRequest !== assessmentRequestId.current) return
        setAssessmentStatus('error')
      })
    }, 180)
    return () => window.clearTimeout(timer)
  }, [dataset, runtime.recommendationEngine, selected])

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
      savePaletteSession({ colors: selected, mode: nextMode, scope: nextScope })
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

  const addColor = useCallback(async (color: PaletteColor) => {
    if (selected.length >= runtime.maxSelections || selected.some((item) => item.id === color.id || item.hex === color.hex)) return
    invalidateResults()
    setNamingCount((count) => count + 1)
    try {
      const namedColor = await runtime.colorNamer.name(color).catch(() => color)
      setSelected((current) => current.length >= runtime.maxSelections || current.some((item) => item.id === namedColor.id || item.hex === namedColor.hex)
        ? current
        : [...current, namedColor])
    } finally {
      setNamingCount((count) => Math.max(0, count - 1))
    }
  }, [invalidateResults, runtime.colorNamer, runtime.maxSelections, selected])

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

  const searchColorNames = useCallback((query: string, limit?: number) => runtime.colorNamer.search(query, limit), [runtime.colorNamer])

  return { dataset, selected, mode, scope, results, assessment, assessmentStatus, status, error, isNaming: namingCount > 0, addColor, removeColor, setMode, setScope, generate, searchColorNames }
}
