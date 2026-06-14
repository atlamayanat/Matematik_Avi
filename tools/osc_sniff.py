"""Tiny UDP sniffer to confirm the detector is sending /hand OSC to port 9000.
Binds 9000, listens ~4s, prints datagram count + a decoded sample.
If the bind fails with WinError 10048, something else (Unity?) already owns 9000.
"""
import socket
import struct
import sys
import time

PORT = 9000


def decode_osc(data: bytes):
    """Minimal OSC decode: address, typetags, args (f/i/s)."""
    def pad(n):  # OSC strings/blobs are 4-byte aligned
        return (n + 3) & ~3
    i = data.find(b"\x00")
    addr = data[:i].decode("ascii", "replace")
    p = pad(i + 1)
    if p >= len(data) or data[p:p+1] != b",":
        return addr, None
    j = data.find(b"\x00", p)
    tags = data[p+1:j].decode("ascii", "replace")
    p = pad(j + 1)
    args = []
    for t in tags:
        if t == "f":
            args.append(round(struct.unpack(">f", data[p:p+4])[0], 3)); p += 4
        elif t == "i":
            args.append(struct.unpack(">i", data[p:p+4])[0]); p += 4
        elif t == "s":
            k = data.find(b"\x00", p)
            args.append(data[p:k].decode("ascii", "replace")); p = pad(k + 1)
    return addr, args


def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(("0.0.0.0", PORT))
    except OSError as e:
        print(f"BIND FAILED on {PORT}: {e}")
        print("-> Port 9000 is already in use (likely Unity is in Play and listening).")
        sys.exit(2)
    s.settimeout(0.5)
    print(f"Listening on UDP {PORT} for 4s...")
    n = 0
    sample = None
    present_seen = set()
    t0 = time.monotonic()
    while time.monotonic() - t0 < 4.0:
        try:
            data, addr = s.recvfrom(2048)
        except socket.timeout:
            continue
        n += 1
        a, args = decode_osc(data)
        if sample is None:
            sample = (a, args)
        if args and len(args) >= 3:
            present_seen.add(args[2])
    s.close()
    print(f"Received {n} datagrams in 4s.")
    if sample:
        print(f"Sample: addr={sample[0]} args={sample[1]}")
        print(f"present values seen: {sorted(present_seen)}  (1 = hand detected, 0 = absent)")
    else:
        print("NO packets received -> the detector is NOT sending.")


if __name__ == "__main__":
    main()
