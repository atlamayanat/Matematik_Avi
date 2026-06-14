"""Gönderici (sender) katmanı: OSC (Unity) ve/veya WebSocket (tarayıcı).

create_sender(cfg) config.json'daki net.transport'a göre seçer:
    "osc"  (varsayılan, geriye uyumlu) -> OscSender        (Unity)
    "ws"                               -> WsSender          (tarayıcı)
    "both"                             -> CompositeSender   (ikisi birden)

Hepsi aynı arayüzü sunar: send_hand(nx,ny,present,gesture) / send_absent(last_nx,last_ny).
websockets bağımlılığı yalnızca ws|both seçildiğinde import edilir; eski 'osc'
kurulumları websockets kurulmadan çalışmaya devam eder.
"""

class CompositeSender:
    """Birden çok göndericiye aynı çağrıyı iletir (transport='both')."""

    def __init__(self, senders):
        self._senders = [s for s in senders if s is not None]

    def send_hand(self, nx, ny, present, gesture):
        for s in self._senders:
            s.send_hand(nx, ny, present, gesture)

    def send_absent(self, last_nx, last_ny):
        for s in self._senders:
            s.send_absent(last_nx, last_ny)

    def close(self):
        for s in self._senders:
            close = getattr(s, "close", None)
            if callable(close):
                close()


def create_sender(cfg):
    net = cfg.get("net", None)
    transport = str(getattr(net, "transport", "osc") if net is not None else "osc").lower()

    if transport in ("ws", "both"):
        from .ws_sender import WsSender  # lazy: websockets sadece burada gerekir
        ws = WsSender(cfg)
        if transport == "ws":
            return ws
        from .osc_sender import OscSender  # lazy: pythonosc sadece osc|both'ta gerekir
        return CompositeSender([OscSender(cfg), ws])

    from .osc_sender import OscSender      # "osc" / varsayılan / bilinmeyen
    return OscSender(cfg)                   # -> mevcut Unity davranışı


def __getattr__(name):  # `from net import OscSender` hâlâ çalışsın (tembel; pythonosc gerektirmez)
    if name == "OscSender":
        from .osc_sender import OscSender
        return OscSender
    if name == "WsSender":
        from .ws_sender import WsSender
        return WsSender
    raise AttributeError(f"module 'net' has no attribute {name!r}")


__all__ = ["OscSender", "WsSender", "CompositeSender", "create_sender"]
