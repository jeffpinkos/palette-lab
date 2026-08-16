from __future__ import annotations

import math


def _linear_channel(channel: int) -> float:
    value = channel / 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def rgb_to_oklab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    red, green, blue = (_linear_channel(channel) for channel in rgb)
    l = 0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue
    m = 0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue
    s = 0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue
    l_root, m_root, s_root = math.cbrt(l), math.cbrt(m), math.cbrt(s)
    return (
        0.2104542553 * l_root + 0.7936177850 * m_root - 0.0040720468 * s_root,
        1.9779984951 * l_root - 2.4285922050 * m_root + 0.4505937099 * s_root,
        0.0259040371 * l_root + 0.7827717662 * m_root - 0.8086757660 * s_root,
    )


def rgb_to_oklch(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    lightness, a, b = rgb_to_oklab(rgb)
    return lightness, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def _srgb_channel(channel: float) -> int:
    value = 12.92 * channel if channel <= 0.0031308 else 1.055 * max(channel, 0) ** (1 / 2.4) - 0.055
    return round(max(0.0, min(1.0, value)) * 255)


def _oklch_to_linear_rgb(lightness: float, chroma: float, hue: float) -> tuple[float, float, float]:
    radians = math.radians(hue)
    a, b = chroma * math.cos(radians), chroma * math.sin(radians)
    l_root = lightness + 0.3963377774 * a + 0.2158037573 * b
    m_root = lightness - 0.1055613458 * a - 0.0638541728 * b
    s_root = lightness - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_root ** 3, m_root ** 3, s_root ** 3
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


def oklch_to_rgb(lightness: float, chroma: float, hue: float) -> tuple[int, int, int]:
    """Convert OKLCH to clipped sRGB, preserving exact in-gamut round trips."""
    return tuple(_srgb_channel(channel) for channel in _oklch_to_linear_rgb(lightness, chroma, hue))


def oklch_to_gamut_mapped_rgb(lightness: float, chroma: float, hue: float, iterations: int = 18) -> tuple[int, int, int]:
    """Map an OKLCH color into sRGB by reducing chroma while preserving L and hue.

    Channel clipping changes hue unpredictably. A monotone binary search along the
    constant-lightness, constant-hue ray instead finds the highest in-gamut chroma.
    """
    channels = _oklch_to_linear_rgb(lightness, chroma, hue)
    if all(0.0 <= channel <= 1.0 for channel in channels):
        return tuple(_srgb_channel(channel) for channel in channels)
    low, high = 0.0, max(0.0, chroma)
    for _ in range(max(1, iterations)):
        midpoint = (low + high) / 2
        candidate = _oklch_to_linear_rgb(lightness, midpoint, hue)
        if all(0.0 <= channel <= 1.0 for channel in candidate):
            low = midpoint
        else:
            high = midpoint
    return tuple(_srgb_channel(channel) for channel in _oklch_to_linear_rgb(lightness, low, hue))


def perceptual_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    left_lab, right_lab = rgb_to_oklab(left), rgb_to_oklab(right)
    raw = math.sqrt(sum((a - b) ** 2 for a, b in zip(left_lab, right_lab)))
    return min(1.0, raw / 0.75)


def hue_distance(left: float, right: float) -> float:
    difference = abs(left - right) % 360
    return min(difference, 360 - difference)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb
