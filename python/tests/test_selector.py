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


def test_acquire_locks_nearest_in_depth_not_larger_idle(cfg):
    s = sel(cfg)
    near = hand(0.40, 0.5, 0.12, 1.0)   # oynama eli: daha yakın, foreshorten -> küçük
    far = hand(0.60, 0.5, 0.20, 1.6)    # boştaki el: daha uzak ama BÜYÜK span
    r = s.update([near, far])
    assert r.locked is near             # derinlik boyutu yener


def test_acquire_ambiguity_waits_not_lock_far_idle(cfg):
    s = sel(cfg)
    near_nodepth = hand(0.40, 0.5, 0.20, None)   # oynama eli büyük ama derinliği düştü
    far_depth = hand(0.60, 0.5, 0.10, 1.6)       # boştaki el küçük, derinliği var
    r = s.update([near_nodepth, far_depth])
    assert r.locked is None                       # belirsiz -> uzak ele kilitlenmez, bekler
    # derinlik dönünce yakın ele kilitlenir
    near_back = hand(0.40, 0.5, 0.20, 1.0)
    r = s.update([near_back, far_depth])
    assert r.locked is near_back


def test_idle_hand_cannot_inherit_lock_via_depth_gate(cfg):
    s = sel(cfg)
    play = hand(0.5, 0.5, 0.15, 1.0)
    s.update([play])                                     # oynama elini kilitle
    idle = hand(0.52, 0.5, 0.30, 1.7)                    # boştaki el XY'de çok yakın görünür
    r = s.update([idle])                                 # ama dz>assoc_max_dz -> DEVRALAMAZ
    assert r.locked is play and r.coasted


def test_depth_known_lock_not_stolen_by_big_depthless_idle(cfg):
    s = sel(cfg)
    play = hand(0.4, 0.5, 0.12, 1.0)
    s.update([play])
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
    s.update([play])
    other_nearer = hand(0.7, 0.5, 0.14, 0.8)             # steal_z_margin'den fazla yakın
    switched = False
    for _ in range(int(cfg.active_player.steal_frames) + 3):
        r = s.update([hand(0.4, 0.5, 0.12, 1.2), other_nearer])
        if r.just_acquired:
            switched = True
    assert switched                                      # bilerek el değiştirme çalışır


def test_dropout_coasts_and_flags_coasted(cfg):
    s = sel(cfg)
    s.update([hand(0.5, 0.5, 0.15, 1.0)])
    r = s.update([])                                     # bu karede kimse algılanmadı
    assert r.locked is not None and r.coasted            # bayat jest FSM'e beslenmesin diye

def test_lone_far_hand_still_selectable(cfg):
    s = sel(cfg)
    far = hand(0.5, 0.5, 0.03, 2.8)                      # küçük/uzak ama tek el
    r = s.update([far])
    assert r.locked is far                               # mesafe kilidi yok
