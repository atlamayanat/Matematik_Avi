"""Onbelleksiz statik web sunucu + telemetri kayit ucu (kiosk icin).

Statik servis: index.html surum-busted DEGIL (assetler ?v=N ile busted ama HTML
degil). `python -m http.server` Cache-Control gondermedigi icin Chrome (kalici
profil) eski index.html'i onbellekten sunup ESKI surumu calistiriyor. Cozum:
her yanitta no-store gonder; tarayici HTML'i hic onbellege almasin.

Telemetri: oyun (web/js/telemetry.js) olaylari POST /telemetry ile gonderir;
her olay data\\telemetry\\events_YYYYMMDD.jsonl dosyasina TEK SATIR JSON olarak
eklenir. Rapor icin: kokteki Rapor.bat (tools/rapor.py). Kayit ucu oyunu asla
kilitlemez: bozuk govde bile 204 ile yutulur (istemci ayni bozuk paketi sonsuza
kadar yeniden denemesin), yalnizca DISK yazma hatasi 500 dondurur (yeniden
deneme mantikli oldugu tek durum).

Kullanim:  python serve_nocache.py <port> <web-dizini> [veri-dizini]
           (veri-dizini varsayilani: <repo>/data/telemetry)
"""
import json
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_BODY = 1_000_000          # tek POST govdesi tavani (~1 MB; normal parti < 50 KB)
_write_lock = threading.Lock()  # ThreadingHTTPServer -> es zamanli POST'lar tek dosyaya yazar

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "telemetry"


def _append_events(events, extra):
    """Olaylari gunun .jsonl dosyasina ekle (her olay tek satir, utf-8)."""
    # Klasor calisirken silinmis olabilir (operator data\'yi temizler): kendini
    # onar, yoksa her POST restart'a kadar 500 dongusune girer ve veri kaybolur.
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / time.strftime("events_%Y%m%d.jsonl")
    srv_t = int(time.time())
    with _write_lock:
        with open(path, "a", encoding="utf-8") as f:
            for ev in events:
                if not isinstance(ev, dict):
                    ev = {"type": "_nondict", "raw": str(ev)[:200]}
                ev["srv_t"] = srv_t
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
            if extra:
                extra["srv_t"] = srv_t
                f.write(json.dumps(extra, ensure_ascii=False) + "\n")


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/telemetry":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            # Govdesiz/asiri buyuk istek: yut (413 istemciyi ayni paketle dongulere sokar).
            self._respond(204)
            return
        body = self.rfile.read(length)
        try:
            data = json.loads(body.decode("utf-8", errors="replace"))
            if isinstance(data, list):                 # beacon sade dizi gonderebilir
                events, extra = data, None
            elif isinstance(data, dict):
                events = data.get("events") or []
                extra = None
                if data.get("dropped"):                # istemci tavani asti; kayip miktarini not et
                    extra = {"type": "_dropped", "n": data["dropped"],
                             "sid": data.get("sid", "?")}
            else:
                events, extra = [{"type": "_bad", "raw": str(data)[:200]}], None
        except (ValueError, UnicodeDecodeError):
            events = [{"type": "_bad", "raw": body[:200].decode("utf-8", errors="replace")}]
            extra = None
        try:
            _append_events(events, extra)
        except OSError as exc:                          # disk dolu/kilitli: yeniden denemeye deger
            print(f"[serve_nocache] telemetri yazilamadi: {exc}", flush=True)
            self._respond(500)
            return
        self._respond(204)

    def _respond(self, code):
        self.send_response(code)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass  # kiosk: konsolu kirletme

    def log_error(self, *args):
        pass


def main():
    global DATA_DIR
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    directory = sys.argv[2] if len(sys.argv) > 2 else "."
    if len(sys.argv) > 3:
        DATA_DIR = Path(sys.argv[3])
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    handler = partial(NoCacheHandler, directory=directory)
    httpd = ThreadingHTTPServer(("0.0.0.0", port), handler)
    print(f"[serve_nocache] http://0.0.0.0:{port}  dir={directory}  (no-store)  "
          f"telemetri={DATA_DIR}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
