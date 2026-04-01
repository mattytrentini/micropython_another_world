"""Resource loader for Another World.

Supports two data formats:
  - DOS: memlist.bin + bank01-bank0d (ByteKiller compressed)
  - 20th Anniversary Edition: game/DAT/FILE###.DAT (unpacked individual files)

Auto-detects the format based on which files are present.
"""

import struct

from .consts import (
    GAME_PARTS, RT_SOUND, RT_MUSIC, RT_BITMAP, RT_PALETTE,
    RT_BYTECODE, RT_SHAPE, STATUS_NULL, STATUS_LOADED, STATUS_TOLOAD,
)
from .bytekiller import unpack as bk_unpack


# memlist.bin entry size
MEMENTRY_SIZE = 20

# Data format types
FMT_DOS = "dos"
FMT_20TH = "20th"

# Max resource entries (20th edition has up to 178)
MAX_ENTRIES = 178


class MemEntry:
    """A single resource catalog entry."""
    __slots__ = (
        "status", "res_type", "rank_num", "bank_num",
        "bank_pos", "packed_size", "unpacked_size", "buf",
    )

    def __init__(self):
        self.status = STATUS_NULL
        self.res_type = 0
        self.rank_num = 0
        self.bank_num = 0
        self.bank_pos = 0
        self.packed_size = 0
        self.unpacked_size = 0
        self.buf = None  # bytearray of loaded data


class Resource:
    """Resource manager: catalog, bank reader, part loader.

    Auto-detects data format (DOS or 20th Anniversary Edition).
    """

    def __init__(self, file_hal):
        self.file_hal = file_hal
        self.mem_list = []
        self.num_entries = 0
        self.data_format = None

        # Segment pointers for current part
        self.seg_palette = None
        self.seg_code = None
        self.seg_video1 = None
        self.seg_video2 = None

        self.current_part = 0

    def detect_format(self):
        """Auto-detect the game data format.

        Checks for 20th Anniversary Edition first (game/DAT/FILE017.DAT),
        then falls back to DOS format (memlist.bin).
        """
        # Check for 20th Anniversary Edition
        if self.file_hal.file_exists("game/DAT/FILE017.DAT"):
            self.data_format = FMT_20TH
            return FMT_20TH

        # Check for DOS format
        if (self.file_hal.file_exists("memlist.bin") or
                self.file_hal.file_exists("MEMLIST.BIN")):
            self.data_format = FMT_DOS
            return FMT_DOS

        raise RuntimeError(
            "No game data found. Expected either:\n"
            "  - game/DAT/FILE017.DAT (20th Anniversary Edition)\n"
            "  - memlist.bin (DOS version)"
        )

    def read_memlist(self):
        """Initialize the resource catalog.

        For DOS: parses memlist.bin.
        For 20th Anniversary: creates entries for FILE###.DAT files.
        """
        if self.data_format is None:
            self.detect_format()

        if self.data_format == FMT_20TH:
            self._init_20th()
        else:
            self._read_memlist_dos()

    def _init_20th(self):
        """Initialize resource entries for 20th Anniversary Edition.

        Creates placeholder entries for each FILE###.DAT that exists.
        """
        self.mem_list = [MemEntry() for _ in range(MAX_ENTRIES)]
        self.num_entries = MAX_ENTRIES

        # Scan for existing files and mark them as loadable
        for i in range(MAX_ENTRIES):
            path = "game/DAT/FILE{:03d}.DAT".format(i)
            if self.file_hal.file_exists(path):
                self.mem_list[i].bank_num = 1  # non-zero = loadable
                self.mem_list[i].rank_num = 1

    def _read_memlist_dos(self):
        """Parse memlist.bin for DOS format."""
        data = self.file_hal.read_file("memlist.bin")
        if data is None:
            data = self.file_hal.read_file("MEMLIST.BIN")
        if data is None:
            raise RuntimeError("Cannot find memlist.bin")

        self.mem_list = []
        offset = 0
        while offset + MEMENTRY_SIZE <= len(data):
            status = data[offset]
            if status == 0xFF:
                break

            me = MemEntry()
            me.status = status
            me.res_type = data[offset + 1]
            me.rank_num = data[offset + 6]
            me.bank_num = data[offset + 7]
            me.bank_pos = struct.unpack_from(">I", data, offset + 8)[0]
            me.packed_size = struct.unpack_from(">I", data, offset + 12)[0]
            me.unpacked_size = struct.unpack_from(">I", data, offset + 16)[0]

            self.mem_list.append(me)
            offset += MEMENTRY_SIZE

        self.num_entries = len(self.mem_list)

    def invalidate_all(self):
        """Invalidate all loaded resources (free memory)."""
        for me in self.mem_list:
            me.status = STATUS_NULL
            me.buf = None

    def load_or_setup_part(self, res_id):
        """Called by VM opcode 0x19.

        If res_id >= 16000, load a new game part (level).
        Otherwise, load a single resource.
        """
        if res_id >= 16000:
            self.setup_part(res_id)
        else:
            self._load_single(res_id)

    def setup_part(self, part_id):
        """Load a new game part (level)."""
        part_idx = part_id - 16000
        if part_idx < 0 or part_idx >= len(GAME_PARTS):
            raise RuntimeError("Invalid part ID: {}".format(part_id))

        ipal, icod, ivd1, ivd2 = GAME_PARTS[part_idx]

        self.invalidate_all()

        if self.data_format == FMT_20TH:
            self._setup_part_20th(ipal, icod, ivd1, ivd2)
        else:
            self._setup_part_dos(ipal, icod, ivd1, ivd2)

        self.current_part = part_id

    def _setup_part_20th(self, ipal, icod, ivd1, ivd2):
        """Load part resources for 20th Anniversary Edition."""
        self.seg_palette = self._load_dat_file(ipal)
        self.seg_code = self._load_dat_file(icod)
        self.seg_video1 = self._load_dat_file(ivd1)
        if ivd2 != 0:
            self.seg_video2 = self._load_dat_file(ivd2)
        else:
            self.seg_video2 = None

    def _setup_part_dos(self, ipal, icod, ivd1, ivd2):
        """Load part resources for DOS format."""
        self.mem_list[ipal].status = STATUS_TOLOAD
        self.mem_list[icod].status = STATUS_TOLOAD
        self.mem_list[ivd1].status = STATUS_TOLOAD
        if ivd2 != 0:
            self.mem_list[ivd2].status = STATUS_TOLOAD

        self._load_marked()

        self.seg_palette = self.mem_list[ipal].buf
        self.seg_code = self.mem_list[icod].buf
        self.seg_video1 = self.mem_list[ivd1].buf
        if ivd2 != 0:
            self.seg_video2 = self.mem_list[ivd2].buf
        else:
            self.seg_video2 = None

    def _load_single(self, res_id):
        """Load a single resource by ID."""
        if res_id >= self.num_entries:
            return

        if self.data_format == FMT_20TH:
            buf = self._load_dat_file(res_id)
            if buf is not None:
                me = self.mem_list[res_id]
                me.buf = buf
                me.status = STATUS_LOADED
        else:
            self.mem_list[res_id].status = STATUS_TOLOAD
            self._load_marked()

    # --- 20th Anniversary Edition loading ---

    def _load_dat_file(self, res_id):
        """Load a resource from game/DAT/FILE###.DAT.

        Returns bytearray or None.
        """
        path = "game/DAT/FILE{:03d}.DAT".format(res_id)
        if not self.file_hal.file_exists(path):
            return None

        data = self.file_hal.read_file(path)
        if data is not None:
            # Cache in mem_list
            if res_id < self.num_entries:
                self.mem_list[res_id].buf = data
                self.mem_list[res_id].status = STATUS_LOADED
        return data

    # --- DOS format loading ---

    def _load_marked(self):
        """Load all resources marked as STATUS_TOLOAD (DOS format).

        Resources are loaded in rank order (highest rank first).
        """
        while True:
            best = None
            best_rank = -1
            for me in self.mem_list:
                if me.status == STATUS_TOLOAD and me.rank_num > best_rank:
                    best_rank = me.rank_num
                    best = me

            if best is None:
                break

            if best.bank_num == 0:
                best.status = STATUS_NULL
                continue

            buf = self._read_bank(best)
            if buf is not None:
                best.buf = buf
                best.status = STATUS_LOADED
            else:
                best.status = STATUS_NULL

    def _read_bank(self, me):
        """Read and decompress a resource from a bank file (DOS format).

        Returns bytearray of decompressed data, or None on failure.
        """
        bank_name = "bank{:02x}".format(me.bank_num)

        if not self.file_hal.file_exists(bank_name):
            bank_name = bank_name.upper()
            if not self.file_hal.file_exists(bank_name):
                return None

        data = self.file_hal.read_at(bank_name, me.bank_pos, me.packed_size)
        if data is None or len(data) < me.packed_size:
            return None

        if me.packed_size == me.unpacked_size:
            return data
        else:
            return bk_unpack(data, me.packed_size)

    def get_entry(self, res_id):
        """Get a loaded resource entry by ID."""
        if res_id < self.num_entries:
            me = self.mem_list[res_id]
            if me.status == STATUS_LOADED:
                return me
        return None
