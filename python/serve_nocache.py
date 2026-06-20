"""Onbelleksiz statik web sunucu (kiosk icin).

Sorun: index.html surum-busted DEGIL (assetler ?v=N ile busted ama HTML degil).
`python -m http.server` Cache-Control gondermedigi icin Chrome (kalici profil)
eski index.html'i onbellekten sunup ESKI surumu calistiriyor -> kalibrasyon
giris ekrani gelmiyor, direkt BASLA aciliyor. Cozum: her yanitta no-store
gonder; tarayici HTML'i hic onbellege almasin, her acilista taze ceksin.

Kullanim:  python serve_nocache.py <port> <dizin>
"""
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, *args):
        pass  # kiosk: konsolu kirletme


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    directory = sys.argv[2] if len(sys.argv) > 2 else "."
    handler = partial(NoCacheHandler, directory=directory)
    httpd = ThreadingHTTPServer(("0.0.0.0", port), handler)
    print(f"[serve_nocache] http://0.0.0.0:{port}  dir={directory}  (no-store)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
