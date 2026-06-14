"""ws_sniff.py — WebSocket köprüsünün gerçekten kare gönderdiğini doğrular.

osc_sniff.py'nin web karşılığı. Detektörü `net.transport = ws` (veya "both") ile
çalıştır, sonra:

    python tools/ws_sniff.py                 # ws://127.0.0.1:8765, ~4 sn dinle
    python tools/ws_sniff.py --host 192.168.1.50 --port 8765 --seconds 6

Kare gelmiyorsa: dedektör çalışmıyor / yanlış transport / yanlış host:port /
güvenlik duvarı. (Detektör tarafında "[ws] WebSocket köprüsü -> ws://..." satırını gör.)

Gereksinim: pip install websockets
"""

from __future__ import annotations

import argparse
import asyncio
import json

try:
    import websockets
except ImportError:
    raise SystemExit("Bu araç 'websockets' gerektirir:  pip install websockets")


async def sniff(host: str, port: int, seconds: float) -> int:
    url = f"ws://{host}:{port}"
    print(f"[ws_sniff] bağlanılıyor: {url}  ({seconds:.0f} sn dinlenecek)")
    try:
        async with websockets.connect(url, open_timeout=4) as ws:
            print("[ws_sniff] BAĞLANDI. Kareler bekleniyor…")
            count = 0
            gestures = set()
            sample = None
            loop = asyncio.get_event_loop()
            end = loop.time() + seconds
            while loop.time() < end:
                try:
                    remaining = max(0.05, end - loop.time())
                    raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                count += 1
                try:
                    m = json.loads(raw)
                    gestures.add(m.get("gesture"))
                    if sample is None:
                        sample = m
                except Exception:
                    if sample is None:
                        sample = raw

            print(f"[ws_sniff] alınan kare: {count}")
            print(f"[ws_sniff] görülen gesture değerleri: {sorted(g for g in gestures if g)}")
            print(f"[ws_sniff] örnek kare: {sample}")
            if count == 0:
                print("[ws_sniff] UYARI: hiç kare gelmedi — dedektör gönderiyor mu? "
                      "(transport=ws|both ve present?)")
                return 1
            if "open" not in gestures and "fist" not in gestures:
                print("[ws_sniff] UYARI: 'open'/'fist' görülmedi — gesture eşlemesini kontrol et.")
            return 0
    except Exception as exc:
        print(f"[ws_sniff] BAĞLANTI HATASI: {exc}")
        print("[ws_sniff] Detektör çalışıyor mu ve net.transport = ws|both mi?")
        return 2


def main() -> int:
    ap = argparse.ArgumentParser(description="WebSocket /hand köprüsü teşhis aracı")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--seconds", type=float, default=4.0)
    args = ap.parse_args()
    return asyncio.run(sniff(args.host, args.port, args.seconds))


if __name__ == "__main__":
    raise SystemExit(main())
