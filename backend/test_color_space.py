import pytest

from .color_space import hue_distance, oklch_to_gamut_mapped_rgb, oklch_to_rgb, perceptual_distance, rgb_to_hex, rgb_to_oklab, rgb_to_oklch


@pytest.mark.parametrize("rgb", [(0, 0, 0), (255, 255, 255), (255, 0, 0), (18, 171, 239), (200, 255, 0)])
def test_oklch_round_trip_stays_close(rgb):
    lightness, chroma, hue = rgb_to_oklch(rgb)
    rebuilt = oklch_to_rgb(lightness, chroma, hue)
    assert max(abs(left - right) for left, right in zip(rgb, rebuilt)) <= 1


def test_oklab_lightness_has_expected_endpoints():
    assert rgb_to_oklab((0, 0, 0))[0] == pytest.approx(0)
    assert rgb_to_oklab((255, 255, 255))[0] == pytest.approx(1, abs=1e-7)


def test_perceptual_distance_is_symmetric_and_normalized():
    assert perceptual_distance((255, 0, 0), (0, 0, 255)) == perceptual_distance((0, 0, 255), (255, 0, 0))
    assert perceptual_distance((0, 0, 0), (255, 255, 255)) == 1


@pytest.mark.parametrize("left,right,expected", [(10, 350, 20), (0, 180, 180), (45, 45, 0)])
def test_hue_distance_wraps(left, right, expected):
    assert hue_distance(left, right) == expected


def test_rgb_to_hex_is_lowercase_and_padded():
    assert rgb_to_hex((1, 15, 255)) == "#010fff"


@pytest.mark.parametrize("lightness,chroma,hue", [(.6, .5, 210), (.7, .4, 40), (.5, .45, 330), (.8, .3, 120)])
def test_gamut_mapping_preserves_lightness_and_hue(lightness, chroma, hue):
    realized_lightness, realized_chroma, realized_hue = rgb_to_oklch(oklch_to_gamut_mapped_rgb(lightness, chroma, hue))
    assert realized_lightness == pytest.approx(lightness, abs=.005)
    assert hue_distance(realized_hue, hue) < .5
    assert 0 < realized_chroma <= chroma


def test_gamut_mapping_avoids_the_hue_shift_from_channel_clipping():
    target = (.6, .5, 210)
    mapped_hue = rgb_to_oklch(oklch_to_gamut_mapped_rgb(*target))[2]
    clipped_hue = rgb_to_oklch(oklch_to_rgb(*target))[2]
    assert hue_distance(mapped_hue, target[2]) < hue_distance(clipped_hue, target[2])


def test_gamut_mapping_is_deterministic():
    assert oklch_to_gamut_mapped_rgb(.62, .44, 275) == oklch_to_gamut_mapped_rgb(.62, .44, 275)
