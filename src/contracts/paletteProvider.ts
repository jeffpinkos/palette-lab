import type { PaletteDataset } from '@/domain'

export interface PaletteProvider {
  readonly id: string
  load(): Promise<PaletteDataset>
}
