"""Dump game data information for inspection.

Supports both DOS (memlist.bin) and 20th Anniversary Edition (game/DAT/) formats.

Usage:
    python3 tools/dump_memlist.py <data_dir>
    micropython tools/dump_memlist.py <data_dir>

Example:
    python3 tools/dump_memlist.py ./gamedata
"""

import sys
import os
sys.path.insert(0, ".")

from aw.resource import Resource, FMT_DOS, FMT_20TH
from aw.consts import (
    RT_SOUND, RT_MUSIC, RT_BITMAP, RT_PALETTE, RT_BYTECODE, RT_SHAPE,
    GAME_PARTS,
)
from hal_unix.file_unix import UnixFile

TYPE_NAMES = {
    RT_SOUND: "SOUND",
    RT_MUSIC: "MUSIC",
    RT_BITMAP: "BITMAP",
    RT_PALETTE: "PALETTE",
    RT_BYTECODE: "BYTECODE",
    RT_SHAPE: "SHAPE",
    6: "BANK",
}

PART_NAMES = [
    "Copy Protection", "Introduction", "Water", "Prison",
    "Cite", "Arene", "Luxe", "Final", "Password", "Password",
]


def dump_dos(res):
    """Dump DOS format memlist.bin entries."""
    print("Format: DOS (memlist.bin)")
    print("Entries: {}\n".format(res.num_entries))
    print("{:>4s}  {:>4s}  {:>8s}  {:>4s}  {:>4s}  {:>10s}  {:>10s}  {:>10s}".format(
        "ID", "Stat", "Type", "Rank", "Bank", "BankPos", "Packed", "Unpacked"))
    print("-" * 72)

    for i, me in enumerate(res.mem_list):
        type_str = TYPE_NAMES.get(me.res_type, "?{}".format(me.res_type))
        compressed = " *" if me.packed_size != me.unpacked_size else ""
        print("{:4d}  0x{:02X}  {:>8s}  {:4d}  {:4d}  0x{:08X}  {:10d}  {:10d}{}".format(
            i, me.status, type_str, me.rank_num, me.bank_num,
            me.bank_pos, me.packed_size, me.unpacked_size, compressed))

    by_type = {}
    total_packed = 0
    total_unpacked = 0
    for me in res.mem_list:
        t = TYPE_NAMES.get(me.res_type, "OTHER")
        if t not in by_type:
            by_type[t] = [0, 0, 0]
        by_type[t][0] += 1
        by_type[t][1] += me.packed_size
        by_type[t][2] += me.unpacked_size
        total_packed += me.packed_size
        total_unpacked += me.unpacked_size

    print("\n--- Summary ---")
    for t in sorted(by_type.keys()):
        count, packed, unpacked = by_type[t]
        print("  {:>8s}: {:3d} entries, {:7d} bytes packed, {:7d} bytes unpacked".format(
            t, count, packed, unpacked))
    print("  {:>8s}: {:3d} entries, {:7d} bytes packed, {:7d} bytes unpacked".format(
        "TOTAL", res.num_entries, total_packed, total_unpacked))


def dump_20th(res, data_dir):
    """Dump 20th Anniversary Edition data files."""
    print("Format: 20th Anniversary Edition (game/DAT/)")

    # List available FILE###.DAT files
    dat_dir = data_dir + "/game/DAT"
    found = []
    for i in range(178):
        path = "game/DAT/FILE{:03d}.DAT".format(i)
        if res.file_hal.file_exists(path):
            full = data_dir + "/" + path
            try:
                size = os.stat(full)[6]  # st_size
            except (OSError, IndexError):
                size = 0
            found.append((i, size))

    print("Found {} resource files\n".format(len(found)))
    print("{:>4s}  {:>10s}  {:s}".format("ID", "Size", "Filename"))
    print("-" * 40)

    total_size = 0
    for res_id, size in found:
        print("{:4d}  {:10d}  FILE{:03d}.DAT".format(res_id, size, res_id))
        total_size += size

    print("\nTotal: {} bytes ({:.1f} KB)".format(total_size, total_size / 1024))

    # Show which parts are available
    print("\n--- Game Parts ---")
    for idx, (ipal, icod, ivd1, ivd2) in enumerate(GAME_PARTS):
        part_id = 16000 + idx
        name = PART_NAMES[idx] if idx < len(PART_NAMES) else "?"
        avail_ids = [ipal, icod, ivd1]
        if ivd2 != 0:
            avail_ids.append(ivd2)
        present = sum(1 for rid in avail_ids if res.file_hal.file_exists(
            "game/DAT/FILE{:03d}.DAT".format(rid)))
        total = len(avail_ids)
        status = "OK" if present == total else "MISSING {}/{}".format(present, total)
        print("  {:5d}  {:<18s}  res=[{:s}]  {}".format(
            part_id, name,
            ", ".join("{:3d}".format(r) for r in avail_ids),
            status))


def main():
    if len(sys.argv) < 2:
        print("Usage: {} <data_dir>".format(sys.argv[0]))
        sys.exit(1)

    data_dir = sys.argv[1]
    file_hal = UnixFile(data_dir)
    res = Resource(file_hal)

    fmt = res.detect_format()
    res.read_memlist()

    if fmt == FMT_DOS:
        dump_dos(res)
    else:
        dump_20th(res, data_dir)


if __name__ == "__main__":
    main()
