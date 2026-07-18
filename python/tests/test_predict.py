"""main.py'deki saf yardımcılar: 60Hz tahminli ekstrapolasyon, fist-damping ve
derinlik-blob attract tetiği. Donanımsız (saf fonksiyonlar)."""
import numpy as np

from main import _extrapolate, _fist_damp, _approaching


def test_extrapolate_advances_along_velocity():
    # anchor 0.5, hız +1.0/s, lead 0, ufuk 0.1s, dt 0.05s -> +0.05
    x, y = _extrapolate((0.5, 0.5), (1.0, 0.0), 0.0, 0.05, 0.0, 0.1, 1.0, 1.0)
    assert abs(x - 0.55) < 1e-6 and abs(y - 0.5) < 1e-6


def test_extrapolate_caps_at_horizon():
    # 10 sn ileri istense de ufuk 0.05s ile sınırlanır -> +0.05
    x, _ = _extrapolate((0.5, 0.5), (1.0, 0.0), 0.0, 10.0, 0.0, 0.05, 1.0, 1.0)
    assert abs(x - 0.55) < 1e-6


def test_extrapolate_clamps_to_unit():
    # ekrandan uçmasın: [0,1]'e kırpılır
    x, _ = _extrapolate((0.99, 0.5), (10.0, 0.0), 0.0, 0.05, 0.0, 0.1, 1.0, 1.0)
    assert x == 1.0


def test_extrapolate_zero_velocity_holds():
    x, y = _extrapolate((0.4, 0.6), (0.0, 0.0), 0.0, 0.03, 0.024, 0.05, 1.0, 1.0)
    assert x == 0.4 and y == 0.6


class _FakeFSM:
    def __init__(self, ratio):
        self.fist_ratio = ratio


def test_fist_damp_damped_scales_with_ratio():
    assert abs(_fist_damp("damped", _FakeFSM(0.0), "searching") - 1.0) < 1e-6
    assert abs(_fist_damp("damped", _FakeFSM(0.5), "searching") - 0.5) < 1e-6
    assert abs(_fist_damp("damped", _FakeFSM(1.0), "fist") - 0.0) < 1e-6


def test_fist_damp_freeze_on_committed_fist():
    assert _fist_damp("freeze", _FakeFSM(0.0), "fist") == 0.0
    assert _fist_damp("freeze", _FakeFSM(0.0), "searching") == 1.0


def test_fist_damp_off_is_identity():
    assert _fist_damp("off", _FakeFSM(0.9), "fist") == 1.0


def test_approaching_true_when_central_roi_near():
    d = np.full((100, 100), 2.0, dtype=np.float32)   # her yer uzak
    d[30:70, 30:70] = 0.5                            # merkez ROI yakın
    assert _approaching(d, 1.2, 0.04) is True


def test_approaching_false_when_all_invalid():
    d = np.zeros((100, 100), dtype=np.float32)       # tümü 0 = geçersiz
    assert _approaching(d, 1.2, 0.04) is False


def test_approaching_false_when_only_far():
    d = np.full((100, 100), 2.5, dtype=np.float32)   # her yer near_z'den uzak
    assert _approaching(d, 1.2, 0.04) is False
