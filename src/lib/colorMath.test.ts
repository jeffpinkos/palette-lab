import { describe, expect, it } from 'vitest'
import { closestColor, rgbDistance } from './colorMath'
import type { PaletteColor } from '../domain/palette'

const black: PaletteColor = { id: 'black', name: 'Black', hex: '#000000', rgb: [0, 0, 0] }
const white: PaletteColor = { id: 'white', name: 'White', hex: '#ffffff', rgb: [255, 255, 255] }
const red: PaletteColor = { id: 'red', name: 'Red', hex: '#ff0000', rgb: [255, 0, 0] }
const colors = [black, white, red]

describe('closestColor', () => {
  it('returns an exact match', () => expect(closestColor(colors, '#ff0000')).toBe(red))
  it('accepts a hex value without a hash', () => expect(closestColor(colors, 'FFFFFF')).toBe(white))
  it('is case insensitive', () => expect(closestColor(colors, '#Ff0000')).toBe(red))
  it('selects the nearest RGB neighbor', () => expect(closestColor(colors, '#f02020')).toBe(red))
  it.each(['', '#fff', '#gggggg', '#00000000', 'not-a-color'])('rejects invalid value %j', (value) => {
    expect(closestColor(colors, value)).toBeNull()
  })
  it('returns null for an empty palette', () => expect(closestColor([], '#ffffff')).toBeNull())
  it('does not mutate the palette', () => {
    const snapshot = [...colors]
    closestColor(colors, '#101010')
    expect(colors).toEqual(snapshot)
  })
})

describe('rgbDistance', () => {
  it('is zero for the same color', () => expect(rgbDistance(red, red)).toBe(0))
  it('is approximately one across the RGB cube diagonal', () => expect(rgbDistance(black, white)).toBeCloseTo(1, 4))
  it('is symmetric', () => expect(rgbDistance(red, white)).toBeCloseTo(rgbDistance(white, red), 10))
  it('orders closer colors below farther colors', () => {
    expect(rgbDistance(red, { ...red, rgb: [250, 5, 5] })).toBeLessThan(rgbDistance(red, white))
  })
})
