"""GestureFSM (kayan pencere oylaması) birim testleri — donanımsız."""
import pytest

from config import _NS
from gesture import GestureFSM, FIST, SEARCHING


def make(window, fist_votes, open_votes):
    return GestureFSM(_NS({"gesture_fsm": {
        "window": window, "fist_votes": fist_votes, "open_votes": open_votes}}))


def test_commits_fist_after_exactly_fist_votes():
    fsm = make(7, 4, 4)
    for _ in range(3):
        assert fsm.update("Closed_Fist") == SEARCHING   # 3 < 4 oy
    assert fsm.update("Closed_Fist") == FIST             # 4. oy -> yakala


def test_single_open_glitch_does_not_reset_the_vote():
    fsm = make(7, 4, 4)
    for _ in range(3):
        fsm.update("Closed_Fist")                        # fist_n = 3
    fsm.update("Open_Palm")                              # gürültü karesi (fist_n hâlâ 3)
    # Eski "ardışık" kuralı sıfırlardı; pencere oylaması yalnızca seyreltir:
    assert fsm.update("Closed_Fist") == FIST             # fist_n = 4 -> yakala


def test_releases_after_open_votes():
    fsm = make(7, 4, 4)
    for _ in range(7):
        fsm.update("Closed_Fist")
    assert fsm.state == FIST
    st = FIST
    for _ in range(4):
        st = fsm.update("Open_Palm")                     # open_n 4'e ulaşır -> bırak
    assert st == SEARCHING


def test_held_fist_survives_one_open_glitch():
    fsm = make(7, 4, 4)
    for _ in range(7):
        fsm.update("Closed_Fist")
    assert fsm.update("Open_Palm") == FIST               # 1 açık kare bırakmaya yetmez


def test_oscillation_guard_rejects_bad_config():
    with pytest.raises(ValueError):
        make(7, 4, 3)                                    # 4+3 = 7, pencereden büyük DEĞİL


def test_reset_clears_state():
    fsm = make(7, 4, 4)
    for _ in range(7):
        fsm.update("Closed_Fist")
    assert fsm.state == FIST
    fsm.reset()
    assert fsm.state == SEARCHING


def test_shipped_config_commits_within_fist_votes(cfg):
    """Sevk edilen config çocuk yakalaması için yeterince hızlı commit'lemeli."""
    fsm = GestureFSM(cfg)
    commits_at = None
    for i in range(1, 12):
        if fsm.update("Closed_Fist") == FIST:
            commits_at = i
            break
    assert commits_at == int(cfg.gesture_fsm.get("fist_votes", 4))
    assert commits_at <= 5     # ~<=5 çıkarım karesi (@20-30Hz ~<200ms) = "bekleme yok"


def test_shipped_config_releases_promptly_on_loose_open(cfg):
    """Çocuk elini açınca ağ takılı kalmamalı (open_votes=4)."""
    fsm = GestureFSM(cfg)
    for _ in range(int(cfg.gesture_fsm.get("window", 7))):
        fsm.update("Closed_Fist")
    assert fsm.state == FIST
    st = FIST
    for _ in range(int(cfg.gesture_fsm.get("open_votes", 4))):
        st = fsm.update("Open_Palm")
    assert st == SEARCHING
