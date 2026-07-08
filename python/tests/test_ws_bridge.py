"""WebSocket köprüsü ENTEGRASYON testi — ÜRETİM transportu (denetim: hiç test edilmiyordu).
Gerçek WsSender sunucusunu kaldırır, gerçek bir istemci bağlar, tel sözleşmesini doğrular:
{x,y,present,gesture} ve searching->open, fist->fist eşlemesi."""
import asyncio
import json

import pytest

from config import _NS
from net.ws_sender import WsSender

pytest.importorskip("websockets")


def test_ws_wire_contract():
    cfg = _NS({"net": {"transport": "ws", "ws_host": "127.0.0.1", "ws_port": 8799}})
    sender = WsSender(cfg)   # kendi thread'inde sunucu kaldırır, hazır olana bekler
    try:
        asyncio.run(_scenario(sender))
    finally:
        sender.close()


async def _scenario(sender):
    import websockets
    async with websockets.connect("ws://127.0.0.1:8799") as ws:
        # istemcinin sunucuya kaydolmasını bekle (fire-and-forget yayın)
        registered = False
        for _ in range(40):
            sender.send_hand(0.5, 0.5, True, "open")
            try:
                await asyncio.wait_for(ws.recv(), timeout=0.1)
                registered = True
                break
            except asyncio.TimeoutError:
                continue
        assert registered, "istemci WS sunucusuna kaydolamadı"

        # FIST karesi: hedef paket gelene kadar sıradaki eskileri boşalt
        sender.send_hand(0.4, 0.6, True, "fist")
        m = await _recv_until(ws, lambda d: abs(d["x"] - 0.4) < 1e-6)
        assert abs(m["y"] - 0.6) < 1e-6
        assert m["present"] is True and m["gesture"] == "fist"

        # ABSENT: present=False + searching->open eşlemesi
        sender.send_absent(0.4, 0.6)
        m2 = await _recv_until(ws, lambda d: d["present"] is False)
        assert m2["gesture"] == "open"


async def _recv_until(ws, pred):
    for _ in range(40):
        d = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5))
        if pred(d):
            return d
    raise AssertionError("beklenen paket gelmedi")
