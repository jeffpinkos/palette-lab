import { useCallback, useEffect, useState } from 'react'
import type { LabRuntime } from '../config/runtime'
import type { ColorId, HarmonyMode, PaletteColor, PaletteDataset, Recommendation } from '../domain/palette'

export function usePaletteLab(runtime: LabRuntime) {
  const [dataset, setDataset] = useState<PaletteDataset | null>(null)
  const [selectedIds, setSelectedIds] = useState<ColorId[]>([])
  const [mode, setModeState] = useState<HarmonyMode>('balanced')
  const [results, setResults] = useState<Recommendation[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'recommending' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    runtime.paletteProvider.load().then((loaded) => {
      if (!active) return
      setDataset(loaded)
      setSelectedIds(loaded.defaultColorIds?.slice(0, runtime.maxSelections) ?? [])
      setStatus('ready')
    }).catch((reason: unknown) => {
      if (!active) return
      setError(reason instanceof Error ? reason.message : 'Unable to load palette')
      setStatus('error')
    })
    return () => { active = false }
  }, [runtime])

  const generate = useCallback(async (nextMode = mode) => {
    if (!dataset || selectedIds.length === 0) return
    setStatus('recommending')
    setError(null)
    try {
      const nextResults = await runtime.recommendationEngine.recommend({ dataset, selectedColorIds: selectedIds, mode: nextMode, limit: runtime.resultLimit })
      setResults(nextResults)
      setStatus('ready')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to generate recommendations')
      setStatus('error')
    }
  }, [dataset, mode, runtime, selectedIds])

  const addColor = useCallback((color: PaletteColor) => {
    setSelectedIds((current) => current.length < runtime.maxSelections && !current.includes(color.id) ? [...current, color.id] : current)
  }, [runtime.maxSelections])

  const removeColor = useCallback((id: ColorId) => setSelectedIds((current) => current.filter((colorId) => colorId !== id)), [])
  const setMode = useCallback((nextMode: HarmonyMode) => { setModeState(nextMode); if (results.length > 0) void generate(nextMode) }, [generate, results.length])
  const colorsById = new Map(dataset?.colors.map((color) => [color.id, color]) ?? [])
  const selected = selectedIds.flatMap((id) => { const color = colorsById.get(id); return color ? [color] : [] })

  return { dataset, selected, mode, results, status, error, addColor, removeColor, setMode, generate }
}
