"""Yumruk geometrisi (_curled_finger_count) + sample_depth birim testleri.
Çocuk-yumruğu zorunlu gereksiniminin dayandığı saf fonksiyonlar."""
import numpy as np

from detection.recognizer import _curled_finger_count
from camera import sample_depth

_FINGERS = [(5, 6, 7, 8), (9, 10, 11, 12), (13, 14, 15, 16), (17, 18, 19, 20)]


class Pt:
    __slots__ = ("x", "y", "z")
    def __init__(self, x, y, z=0.0):
        self.x = float(x); self.y = float(y); self.z = float(z)


def _hand(shape):
    """shape(fi) -> (pip_y, dip_y, tip_y); mcp hep y=1, wrist orijin."""
    lm = [Pt(0, 0, 0) for _ in range(21)]
    for fi, (mcp, pip, dip, tip) in enumerate(_FINGERS):
        x = float(fi)
        py, dy, ty = shape(fi)
        lm[mcp] = Pt(x, 1); lm[pip] = Pt(x, py); lm[dip] = Pt(x, dy); lm[tip] = Pt(x, ty)
    return lm


def test_open_hand_zero_curled():
    lm = _hand(lambda fi: (2, 3, 4))        # düz uzanan parmaklar
    assert _curled_finger_count(lm, 0.7) == 0


def test_fist_all_four_curled():
    lm = _hand(lambda fi: (2, 1.5, 0.6))    # uç bileğe katlanmış
    assert _curled_finger_count(lm, 0.7) == 4


def test_loose_ratio_is_more_lenient_than_strict():
    # gevşek yarı-kapalı (uç hafif kıvrık): sevk 0.7 sayar, eski katı 0.55 saymaz
    lm = _hand(lambda fi: (2, 2.5, 2.2))
    loose = _curled_finger_count(lm, 0.7)
    strict = _curled_finger_count(lm, 0.55)
    assert loose == 4 and strict == 0


def test_sample_depth_none_and_invalid():
    assert sample_depth(None, 5, 5) is None
    d = np.zeros((50, 50), dtype=np.float32)
    assert sample_depth(d, 200, 200) is None    # kadraj dışı
    assert sample_depth(d, 25, 25) is None       # hepsi 0 = geçersiz


def test_sample_depth_low_percentile_of_valid():
    d = np.zeros((100, 100), dtype=np.float32)
    d[40:61, 40:61] = 1.5                        # elin bölgesi
    v = sample_depth(d, 50, 50)
    assert v is not None and abs(v - 1.5) < 1e-3


def test_sample_depth_prefers_nearer_when_patch_straddles():
    # 11x11 yama arka planı (uzak) + eli (yakın) kapsar; 25. yüzdelik ele yaslanmalı
    d = np.full((100, 100), 3.0, dtype=np.float32)   # arka plan uzak
    d[50:56, 45:56] = 0.8                            # elin yakın kısmı
    v = sample_depth(d, 50, 50)
    assert v is not None and v < 1.5                 # arka plan 3.0 değil, ele yakın


def test_sample_depth_edge_clamps():
    d = np.full((50, 50), 2.0, dtype=np.float32)
    assert abs(sample_depth(d, 0, 0) - 2.0) < 1e-3   # kenarda çökmemeli
