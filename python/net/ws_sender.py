"""WebSocket sender: aynı /hand karesini tarayıcıya JSON olarak yayınlar.

OscSender ile BİREBİR aynı arayüz (send_hand / send_absent), böylece main.py'de
hiçbir mantık değişmeden takılıp çıkarılabilir. CV hattı (homografi, aktif-oyuncu,
One-Euro, FSM) Python'da kalır; tarayıcı yalnızca normalize edilmiş son durumu tüketir.

Tel üzerindeki kontrat (OSC ile aynı semantik, JSON gövde):
    { "x": float[0..1], "y": float[0..1], "present": bool, "gesture": "open"|"fist" }

Tek anlamsal fark: gesture web-kanonik forma çevrilir ("searching" -> "open").
Python iç durumu (gesture.SEARCHING/FIST) DEĞİŞMEZ.

asyncio sunucusu ayrı bir daemon thread'te koşar; ana 60 Hz döngü senkron kalır.
send_hand fire-and-forget yayınlar (latest-value-wins) -> yavaş istemci ana döngüyü
kilitlemez; kare düşürmek güvenlidir.
"""

from __future__ import annotations

import asyncio
import json
import threading

try:
    import websockets
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "WebSocket köprüsü için 'websockets' gerekli. Kur: pip install websockets "
        "(yalnızca config.json net.transport = ws|both iken gerekir)."
    ) from e

from gesture import SEARCHING, FIST


class WsSender:
    def __init__(self, cfg):
        net = cfg.get("net", None)
        self._host = str(getattr(net, "ws_host", "0.0.0.0")) if net is not None else "0.0.0.0"
        self._port = int(getattr(net, "ws_port", 8765)) if net is not None else 8765

        self._clients = set()
        self._loop = None
        self._server = None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="ws-sender", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5.0)  # sunucu kalkana (veya hata verene) kadar kısa bekle

    # ---- asyncio sunucusu (kendi thread'inde) ----
    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        async def _start():
            # serve()'i loop İÇİNDE await et: yeni websockets (v13+) çağrı anında
            # çalışan loop ister; argüman olarak dışarıda değerlendirmek hata verir.
            return await websockets.serve(self._handler, self._host, self._port)

        try:
            self._server = self._loop.run_until_complete(_start())
            print(f"[ws] WebSocket bridge -> ws://{self._host}:{self._port}")
        except Exception as exc:  # port dolu / izin vb. -> köprü pasif, OSC etkilenmez
            print(f"[ws] ERROR: server failed to start ({self._host}:{self._port}): {exc}")
            self._ready.set()
            return
        self._ready.set()
        try:
            self._loop.run_forever()
        finally:
            try:
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            except Exception:
                pass
            self._loop.close()

    async def _handler(self, ws, *args):  # *args: eski websockets sürümlerindeki 'path'
        self._clients.add(ws)
        try:
            await ws.wait_closed()
        finally:
            self._clients.discard(ws)

    async def _broadcast(self, msg: str) -> None:
        if not self._clients:
            return
        await asyncio.gather(
            *(c.send(msg) for c in list(self._clients)),
            return_exceptions=True,  # kapanan/yavaş istemci diğerlerini etkilemesin
        )

    # ---- OscSender ile aynı arayüz ----
    def send_hand(self, nx: float, ny: float, present: bool, gesture: str) -> None:
        # İstemci yoksa ya da loop hazır değilse boşa iş yapma.
        if self._loop is None or not self._clients:
            return
        msg = json.dumps({
            "x": float(nx),
            "y": float(ny),
            "present": bool(present),
            "gesture": "fist" if gesture == FIST else "open",  # searching -> open
        })
        try:
            asyncio.run_coroutine_threadsafe(self._broadcast(msg), self._loop)  # fire-and-forget
        except RuntimeError:
            pass  # loop kapanıyor

    def send_absent(self, last_nx: float, last_ny: float) -> None:
        """Aktif oyuncu yok: kursoru park et, arama durumunu zorla (OscSender ile aynı)."""
        self.send_hand(last_nx, last_ny, False, SEARCHING)

    def close(self) -> None:
        """Sunucuyu temiz kapat ve portu serbest bırak (recalibrate yeniden-başlatması için kritik)."""
        loop = self._loop
        if loop is None or not self._thread.is_alive():
            return

        async def _shutdown():
            if self._server is not None:
                self._server.close()
                await self._server.wait_closed()

        try:
            asyncio.run_coroutine_threadsafe(_shutdown(), loop).result(timeout=2.0)
        except Exception:
            pass
        try:
            loop.call_soon_threadsafe(loop.stop)
        except Exception:
            pass
        self._thread.join(timeout=2.0)
