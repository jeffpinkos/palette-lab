import { describe, expect, it } from 'vitest'
import { RECOMMENDATION_SCOPES } from './options'

describe('RECOMMENDATION_SCOPES', () => {
  it('separates strict Wada companions from archive exploration', () => {
    expect(RECOMMENDATION_SCOPES).toEqual([
      { value: 'companions', label: 'Wada companions' },
      { value: 'palette', label: 'Wada archive' },
      { value: 'spectrum', label: 'Full spectrum' },
    ])
  })
})
