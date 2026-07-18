"""Derinlik-öncelikli ActivePlayerSelector birim testleri — donanımsız.
Denetimin "iki ertelenen bug'ın yaşadığı, %0 kapsamlı bölge" dediği yer."""
from selection import ActivePlayerSelector
from detection.types import HandObservation


def hand(x, y, span, z, gesture="Open_Palm"):
    return HandObservation(
        centroid01=(x, y), centroid_px=(x * 960, y * 540), span01=span,
        gesture=gesture, gesture_score=0.9, handedness="Right",
        detection_score=0.9, landmarks_px=[(int(x * 960), int(y * 540))] * 21,
        z_m=z)


def sel(cfg):
    return ActivePlayerSelector(cfg, cam_res=(960, 540))


def acquire(s, hands, cfg, fps=None):
    """Drive the selector until the acquire-latch hysteresis locks (a provisional
    pick must persist acquire_frames stable frames). Returns the last result."""
    n = max(1, int(cfg.active_player.get("acquire_frames", 1)))
    r = None
    for _ in range(n):
        r = s.update(hands, fps=fps)
    return r


def test_acquire_locks_nearest_in_depth_not_larger_idle(cfg):
    s = sel(cfg)
    near = hand(0.40, 0.5, 0.12, 1.0)   # oynama eli: daha yakın, foreshorten -> küçük
    far = hand(0.60, 0.5, 0.20, 1.6)    # boştaki el: daha uzak ama BÜYÜK span
    r = acquire(s, [near, far], cfg)
    assert r.locked is near             # derinlik boyutu yener


def test_acquire_ambiguity_waits_not_lock_far_idle(cfg):
    s = sel(cfg)
    near_nodepth = hand(0.40, 0.5, 0.20, None)   # oynama eli büyük ama derinliği düştü
    far_depth = hand(0.60, 0.5, 0.10, 1.6)       # boştaki el küçük, derinliği var
    r = s.update([near_nodepth, far_depth])
    assert r.locked is None                       # belirsiz -> uzak ele kilitlenmez, bekler
    # derinlik dönünce yakın ele kilitlenir
    near_back = hand(0.40, 0.5, 0.20, 1.0)
    r = acquire(s, [near_back, far_depth], cfg)
    assert r.locked is near_back


def test_acquire_hysteresis_delays_lock(cfg):
    """acquire_frames>1 iken tek stabil el bile latch için birkaç kare bekletir
    (merkezden geçen bystander'a anlık yanlış-kilit engellenir)."""
    n = int(cfg.active_player.get("acquire_frames", 1))
    if n <= 1:
        return   # histerezis kapalı -> test anlamsız
    s = sel(cfg)
    lone = hand(0.5, 0.5, 0.15, 1.0)
    for _ in range(n - 1):
        assert s.update([lone]).locked is None    # daha latch etmedi
    assert s.update([lone]).locked is lone         # acquire_frames'inci karede kilitlendi


def test_acquire_hysteresis_resets_on_jitter(cfg):
    """Kare kare yer değiştiren (farklı merkez) bir aday latch etmemeli."""
    n = int(cfg.active_player.get("acquire_frames", 1))
    if n <= 1:
        return
    s = sel(cfg)
    # Her kare çok farklı konumda tek el -> anchor sürekli sıfırlanır.
    positions = [(0.2, 0.3), (0.8, 0.7), (0.3, 0.8), (0.7, 0.2), (0.2, 0.7),
                 (0.8, 0.3)]
    locked_any = False
    for (x, y) in positions[:max(n + 2, len(positions))]:
        r = s.update([hand(x, y, 0.15, 1.0)])
        if r.locked is not None:
            locked_any = True
    assert not locked_any


def test_idle_hand_cannot_inherit_lock_via_depth_gate(cfg):
    s = sel(cfg)
    play = hand(0.5, 0.5, 0.15, 1.0)
    acquire(s, [play], cfg)                               # oynama elini kilitle
    idle = hand(0.52, 0.5, 0.30, 1.7)                    # boştaki el XY'de çok yakın görünür
    r = s.update([idle])                                 # ama dz>assoc_max_dz -> DEVRALAMAZ
    assert r.locked is play and r.coasted


def test_depth_known_lock_not_stolen_by_big_depthless_idle(cfg):
    s = sel(cfg)
    play = hand(0.4, 0.5, 0.12, 1.0)
    acquire(s, [play], cfg)
    idle_big_nodepth = hand(0.7, 0.5, 0.40, None)        # kocaman span, derinlik anlık yok
    stole = False
    for _ in range(20):
        r = s.update([hand(0.4, 0.5, 0.12, 1.0), idle_big_nodepth])
        if r.just_acquired:
            stole = True
    assert not stole                                     # kilit derinlikliyken boyutla çalınmaz


def test_intentional_switch_steals_when_other_hand_nearer(cfg):
    s = sel(cfg)
    play = hand(0.4, 0.5, 0.12, 1.2)
    acquire(s, [play], cfg)
    other_nearer = hand(0.7, 0.5, 0.14, 0.8)             # steal_z_margin'den fazla yakın
    switched = False
    for _ in range(int(cfg.active_player.steal_frames) + 3):
        r = s.update([hand(0.4, 0.5, 0.12, 1.2), other_nearer])
        if r.just_acquired:
            switched = True
    assert switched                                      # bilerek el değiştirme çalışır


def test_dropout_coasts_and_flags_coasted(cfg):
    s = sel(cfg)
    acquire(s, [hand(0.5, 0.5, 0.15, 1.0)], cfg)
    r = s.update([])                                     # bu karede kimse algılanmadı
    assert r.locked is not None and r.coasted            # bayat jest FSM'e beslenmesin diye


def test_lone_far_hand_still_selectable(cfg):
    s = sel(cfg)
    far = hand(0.5, 0.5, 0.03, 2.8)                      # küçük/uzak ama tek el
    r = acquire(s, [far], cfg)
    assert r.locked is far                               # mesafe kilidi yok


def test_second_based_lost_threshold_scales_with_fps(cfg):
    """lost_seconds verildiyse ve fps geçilirse, release eşiği kareye saniyeden
    çevrilir (termal fps düşüşünde eşik kaymasın)."""
    ap = cfg.active_player
    lost_s = float(ap.get("lost_seconds", 0.0) or 0.0)
    if lost_s <= 0.0:
        return   # saniye-bazlı kapalı
    fps = 30.0
    expected = max(1, round(lost_s * fps))
    s = sel(cfg)
    acquire(s, [hand(0.5, 0.5, 0.15, 1.0)], cfg, fps=fps)
    released_at = None
    for i in range(1, expected + 5):
        r = s.update([], fps=fps)               # kimse yok -> coast, sonra release
        if r.just_released:
            released_at = i
            break
    assert released_at == expected
