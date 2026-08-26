#!/usr/bin/env python3
"""Keep only the requested sections in a v2fly dlc.dat / geosite.dat.

The upstream builder compiles EVERY list present in the data directory, which
after pruning still includes transitive dependency lists we never route on.
This drops those extra sections so clients download only what the profiles
reference.

Usage: filter-dat.py <in.dat> <out.dat> <SECTION> [<SECTION> ...]
"""

import sys


def read_varint(buf: bytes, i: int):
    shift = val = 0
    while True:
        b = buf[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not b & 0x80:
            return val, i
        shift += 7


def encode_varint(val: int) -> bytes:
    out = bytearray()
    while True:
        b = val & 0x7F
        val >>= 7
        if val:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def fields(buf: bytes):
    i = 0
    while i < len(buf):
        tag, i = read_varint(buf, i)
        fnum, wtype = tag >> 3, tag & 7
        if wtype == 2:
            ln, i = read_varint(buf, i)
            yield fnum, buf[i:i + ln]
            i += ln
        elif wtype == 0:
            v, i = read_varint(buf, i)
            yield fnum, v
        else:
            raise ValueError(f"unsupported wire type {wtype}")


def main() -> int:
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    keep = {s.upper() for s in sys.argv[3:]}

    data = open(src, "rb").read()
    out = bytearray()
    kept = []
    for fnum, payload in fields(data):
        if fnum != 1:
            continue  # GeoSiteList.entry is field 1; ignore unknown fields
        name = next((v.decode() for f, v in fields(payload) if f == 1), "")
        if name not in keep:
            continue
        out += b"\x0a" + encode_varint(len(payload)) + payload
        kept.append(name)

    missing = keep - set(kept)
    if missing:
        print(f"Error: sections missing from input: {', '.join(sorted(missing))}", file=sys.stderr)
        return 1

    open(dst, "wb").write(bytes(out))
    print(f"{dst}: kept {len(kept)} sections ({', '.join(kept)}), {len(out)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
