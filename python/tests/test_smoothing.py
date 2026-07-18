"""One Euro filtresi + CursorSmoother birim testleri."""
from smoothing import CursorSmoother
from smoothing.one_euro import OneEuroFilter


def test_first_sample_passes_through():
    f = OneEuroFilter(1.0, 0.6, 1.0)
    assert f(0.0, 0.5) == 0.5


def test_nonpositive_dt_holds_previous():
    f = OneEuroFilter(1.0, 0.6, 1.0)
    f(1.0, 0.5)
    assert f(1.0, 0.9) == 0.5      # aynı zaman damgası -> önceki tahmin


def test_converges_toward_constant_input():
    f = OneEuroFilter(1.0, 0.0, 1.0)
    x = 0.0
    for i in range(1, 120):
        x = f(i / 60.0, 1.0)
    assert x > 0.9                 # sabit girişe yaklaşır


def test_reset_reinitialises():
    f = OneEuroFilter(1.0, 0.6, 1.0)
    f(0.0, 0.2)
    f.reset()
    assert f(0.0, 0.8) == 0.8      # reset sonrası ilk örnek yeniden geçer


def test_cursor_smoother_two_axis_stays_in_range():
    s = CursorSmoother(1.0, 0.6, 1.0)
    s(0.0, 0.5, 0.5)
    bx, by = s(0.016, 0.6, 0.4)
    assert 0.0 <= bx <= 1.0 and 0.0 <= by <= 1.0


def test_velocity_and_value_exposed_for_extrapolation():
    s = CursorSmoother(1.0, 0.6, 1.0)
    assert s.value() is None            # ilk örnekten önce yok
    s(0.0, 0.5, 0.5)
    s(0.1, 0.7, 0.5)
    vx, vy = s.velocity()
    assert vx > 0.0                     # +x hareket -> pozitif hız tahmini
    assert abs(vy) < 1e-6               # y sabit
    val = s.value()
    assert val is not None and 0.0 <= val[0] <= 1.0
