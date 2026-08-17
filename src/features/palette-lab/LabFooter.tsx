import type { PaletteMetadata } from '@/domain'

type Props = {
  metadata: PaletteMetadata
  colorCount: number
  groupCount: number
  colorNameCount: number
}

export function LabFooter({ metadata, colorCount, groupCount, colorNameCount }: Props) {
  return <footer className="footer"><span className="mark">⊕</span><span>Based on <b>{colorCount}</b> colors and <b>{groupCount}</b> {metadata.groupLabel}</span><span>{colorNameCount.toLocaleString()} Color Name List names · {metadata.attribution}</span></footer>
}
