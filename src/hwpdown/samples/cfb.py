"""Minimal compound-file (CFB / OLE) writer, version 3 (512-byte sectors), for test documents.

Follows the public [MS-CFB] layout: header, FAT, directory, mini FAT and mini stream for streams
smaller than 4096 bytes. Timestamps are zero so the output is deterministic.
"""
from __future__ import annotations

import struct

SECTOR = 512
MINI = 64
CUTOFF = 4096
FREE, ENDCHAIN, FATSECT = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD
NOSTREAM = 0xFFFFFFFF


def _cmp_key(name: str) -> tuple[int, str]:
    return (len(name), name.upper())


def build_cfb(streams: dict[tuple[str, ...], bytes]) -> bytes:
    """Build a CFB file. ``streams`` maps a path such as ``("BodyText", "Section0")`` to its bytes."""
    # -- directory entries (index 0 is the root) -------------------------------------------
    entries: list[dict] = [{"name": "Root Entry", "type": 5, "children": {}, "data": None}]
    for path, data in sorted(streams.items()):
        node = entries[0]
        for part in path[:-1]:
            nxt = node["children"].get(part)
            if nxt is None:
                nxt = {"name": part, "type": 1, "children": {}, "data": None}
                node["children"][part] = nxt
                entries.append(nxt)
            node = nxt
        leaf = {"name": path[-1], "type": 2, "children": {}, "data": data}
        node["children"][path[-1]] = leaf
        entries.append(leaf)
    for i, e in enumerate(entries):
        e["id"] = i
        e["left"] = e["right"] = e["child"] = NOSTREAM

    def link(parent: dict) -> None:
        kids = sorted(parent["children"].values(), key=lambda k: _cmp_key(k["name"]))

        def bst(lo: int, hi: int):
            if lo >= hi:
                return None
            mid = (lo + hi) // 2
            node = kids[mid]
            left, right = bst(lo, mid), bst(mid + 1, hi)
            node["left"] = left["id"] if left else NOSTREAM
            node["right"] = right["id"] if right else NOSTREAM
            return node

        root = bst(0, len(kids))
        parent["child"] = root["id"] if root else NOSTREAM
        for k in kids:
            link(k)

    link(entries[0])

    # -- split streams into mini / regular ---------------------------------------------------
    mini_stream = bytearray()
    mini_fat: list[int] = []
    for e in entries:
        if e["type"] != 2:
            continue
        data = e["data"]
        e["size"] = len(data)
        if not data:
            e["start"] = ENDCHAIN
        elif len(data) < CUTOFF:
            n = -(-len(data) // MINI)
            e["start"] = len(mini_fat)
            mini_fat.extend(list(range(len(mini_fat) + 1, len(mini_fat) + n)) + [ENDCHAIN])
            mini_stream += data + b"\0" * (n * MINI - len(data))
    entries[0]["size"] = len(mini_stream)

    n_dir = -(-len(entries) * 128 // SECTOR)
    n_minifat = -(-len(mini_fat) * 4 // SECTOR) if mini_fat else 0
    n_ministream = -(-len(mini_stream) // SECTOR)
    big = [e for e in entries if e["type"] == 2 and len(e["data"]) >= CUTOFF]
    n_big = sum(-(-len(e["data"]) // SECTOR) for e in big)
    n_fat = 1
    while n_fat * 128 < n_fat + n_dir + n_minifat + n_ministream + n_big:
        n_fat += 1
    if n_fat > 109:
        raise ValueError("test CFB writer supports at most 109 FAT sectors (about 7 MB)")

    fat = [FREE] * (n_fat * 128)
    nxt = 0
    for i in range(n_fat):
        fat[i] = FATSECT
    nxt = n_fat

    def chain(count: int) -> int:
        nonlocal nxt
        start = nxt
        for i in range(count):
            fat[nxt + i] = nxt + i + 1 if i < count - 1 else ENDCHAIN
        nxt += count
        return start

    dir_start = chain(n_dir)
    minifat_start = chain(n_minifat) if n_minifat else ENDCHAIN
    ministream_start = chain(n_ministream) if n_ministream else ENDCHAIN
    entries[0]["start"] = ministream_start
    body = bytearray()
    for e in big:
        count = -(-len(e["data"]) // SECTOR)
        e["start"] = chain(count)
        body += e["data"] + b"\0" * (count * SECTOR - len(e["data"]))

    # -- serialise ----------------------------------------------------------------------------
    dir_bytes = bytearray()
    for e in entries:
        name = e["name"].encode("utf-16-le")
        dir_bytes += name.ljust(64, b"\0")
        dir_bytes += struct.pack("<HBB", len(name) + 2, e["type"], 1)
        dir_bytes += struct.pack("<III", e["left"], e["right"], e["child"])
        dir_bytes += b"\0" * 16 + struct.pack("<I", 0) + b"\0" * 16  # clsid, state, times
        dir_bytes += struct.pack("<IQ", e.get("start", 0) if e["type"] != 1 else 0, e.get("size", 0))
    dir_bytes = dir_bytes.ljust(n_dir * SECTOR, b"\0")
    # unused directory slots must be marked free-ish (type 0, no siblings)
    for off in range(len(entries) * 128, len(dir_bytes), 128):
        dir_bytes[off + 68:off + 80] = struct.pack("<III", NOSTREAM, NOSTREAM, NOSTREAM)

    minifat_bytes = struct.pack(f"<{len(mini_fat)}I", *mini_fat).ljust(n_minifat * SECTOR, b"\xff")
    ministream_bytes = bytes(mini_stream).ljust(n_ministream * SECTOR, b"\0")
    fat_bytes = struct.pack(f"<{len(fat)}I", *fat)

    difat = list(range(n_fat)) + [FREE] * (109 - n_fat)
    header = bytearray()
    header += bytes.fromhex("d0cf11e0a1b11ae1") + b"\0" * 16
    header += struct.pack("<HHHHH", 0x3E, 3, 0xFFFE, 9, 6) + b"\0" * 6
    header += struct.pack("<IIIII", 0, n_fat, dir_start, 0, CUTOFF)
    header += struct.pack("<IIII", minifat_start, n_minifat, ENDCHAIN, 0)
    header += struct.pack("<109I", *difat)
    assert len(header) == 512
    return bytes(header) + fat_bytes + bytes(dir_bytes) + minifat_bytes + ministream_bytes + bytes(body)
