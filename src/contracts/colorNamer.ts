import type { PaletteColor } from '../domain/palette'

/** Names arbitrary colors without coupling the palette or recommendation engine to a catalog. */
export interface ColorNamer {
  readonly count: number
  prepare(): Promise<void>
  name(color: PaletteColor): Promise<PaletteColor>
  search(query: string, limit?: number): Promise<PaletteColor[]>
}
