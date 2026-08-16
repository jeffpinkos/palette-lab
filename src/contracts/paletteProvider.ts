import type { PaletteDataset } from '../domain/palette'

export interface PaletteProvider {
  readonly id: string
  load(): Promise<PaletteDataset>
}
