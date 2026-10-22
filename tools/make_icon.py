#!/usr/bin/env python3
"""Genere l'icone PNG 128x128 de Debloat Android (stdlib uniquement).

Usage : python3 tools/make_icon.py sorties/icon.png
Design : fond sombre, cercle vert (retrait propre), barre horizontale
centree blanche (le "debloat", puissance de retrait).
"""
import struct
import sys
import zlib

SIZE = 128
BG = (13, 17, 23, 255)          # fond sombre
GREEN = (21, 122, 38, 255)      # vert du retrait sur
BAR = (238, 244, 249, 255)      # barre blanche


def render() -> bytes:
    cx = cy = (SIZE - 1) / 2.0
    r_outer = 46.0
    r_inner = 40.0
    rows = bytearray()
    for y in range(SIZE):
        rows.append(0)                      # filtre 0 (None)
        for x in range(SIZE):
            dx = x - cx
            dy = y - cy
            d2 = dx * dx + dy * dy
            px = BG
            if r_inner <= d2 <= r_outer:
                px = GREEN
            elif d2 < r_inner:
                # barre horizontale au centre : |dy| du centre ~ <= 7
                if abs(dy) <= 6.0 and abs(dx) <= r_outer - 12.0:
                    px = BAR
                else:
                    px = GREEN
            rows.extend(px)
    return bytes(rows)


def chunks(data: bytes, size: int = 1 << 20):
    for i in range(0, len(data), size):
        yield data[i:i + size]


def write_png(path: str) -> None:
    ihdr = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        body = tag + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(
            ">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    compress = b"".join(chunks(zlib.compress(render(), 9)))
    png += chunk(b"IDAT", compress)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python3 tools/make_icon.py <fichier.png>", file=sys.stderr)
        sys.exit(1)
    write_png(sys.argv[1])
    print("icone ecrite :", sys.argv[1])
