import type { PaletteMetadata } from '@/domain'

type Props = {
  metadata: PaletteMetadata
  groupCount: number
}

export function LabHeader({ metadata, groupCount }: Props) {
  return <header className="site-header">
    <a className="brand" href="#top">{metadata.name}</a>
    <nav><a className="active" href="#lab">Palette laboratory</a><a href="#method">About the method</a></nav>
    <div className="edition"><span>◉</span><b>{metadata.editionLabel ?? `${groupCount} combinations`}</b></div>
  </header>
}
