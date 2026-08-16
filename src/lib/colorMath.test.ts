import { describe, expect, it } from 'vitest'
import { closestColor, colorFromHex, normalizeHex, perceptualDistance, rgbDistance, rgbToOklab } from './colorMath'
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

describe('normalizeHex', () => {
  it('adds a missing hash and lowercases', () => expect(normalizeHex('ABCDEF')).toBe('#abcdef'))
  it('preserves a valid normalized value', () => expect(normalizeHex('#123456')).toBe('#123456'))
  it('rejects shorthand hex', () => expect(normalizeHex('#fff')).toBeNull())
})

describe('colorFromHex', () => {
  it('returns a known palette color only for an exact match', () => expect(colorFromHex(colors, '#ff0000')).toBe(red))
  it('preserves a non-palette hex exactly', () => expect(colorFromHex(colors, '#f02020')).toMatchObject({ id: 'custom:#f02020', hex: '#f02020', rgb: [240, 32, 32] }))
  it('marks arbitrary colors as custom metadata', () => expect(colorFromHex(colors, '#123456')?.metadata).toEqual({ custom: true }))
  it('works with an empty reference palette', () => expect(colorFromHex([], '#123456')).toMatchObject({ hex: '#123456' }))
  it('rejects invalid input', () => expect(colorFromHex(colors, 'nope')).toBeNull())
})

describe('rgbDistance', () => {
  it('is zero for the same color', () => expect(rgbDistance(red, red)).toBe(0))
  it('is approximately one across the RGB cube diagonal', () => expect(rgbDistance(black, white)).toBeCloseTo(1, 4))
  it('is symmetric', () => expect(rgbDistance(red, white)).toBeCloseTo(rgbDistance(white, red), 10))
  it('orders closer colors below farther colors', () => {
    expect(rgbDistance(red, { ...red, rgb: [250, 5, 5] })).toBeLessThan(rgbDistance(red, white))
  })
})

describe('perceptual color math', () => {
  it('maps black and white to the OKLab lightness endpoints', () => {
    expect(rgbToOklab(black)[0]).toBeCloseTo(0, 6)
    expect(rgbToOklab(white)[0]).toBeCloseTo(1, 6)
  })
  it('is zero for identical colors', () => expect(perceptualDistance(red, red)).toBe(0))
  it('is symmetric and normalized', () => {
    expect(perceptualDistance(red, white)).toBeCloseTo(perceptualDistance(white, red), 10)
    expect(perceptualDistance(black, white)).toBe(1)
  })
})
