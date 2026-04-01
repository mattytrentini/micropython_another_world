"""ByteKiller decompression algorithm.

Used to decompress resources stored in bank files.
The algorithm reads from the end of the packed data backwards,
using a bit stream to determine literal bytes vs back-references.

Translated from bank.cpp in the reference implementation.
"""

import struct


def unpack(src, packed_size):
    """Decompress ByteKiller packed data.

    Args:
        src: bytearray of packed data (at least packed_size bytes).
        packed_size: number of packed bytes.

    Returns:
        bytearray of decompressed data, or None on CRC failure.
    """
    ctx = _UnpackCtx()

    # Read from end of packed data
    ip = packed_size - 4
    ctx.datasize = _read_be_u32(src, ip)
    ip -= 4
    ctx.crc = _read_be_u32(src, ip)
    ip -= 4
    ctx.chk = _read_be_u32(src, ip)
    ip -= 4
    ctx.crc ^= ctx.chk

    dst = bytearray(ctx.datasize)
    op = ctx.datasize - 1  # output position (write backwards)

    while ctx.datasize > 0:
        cf, ip = _next_chunk(ctx, src, ip)
        if not cf:
            ctx.size = 1
            cf, ip = _next_chunk(ctx, src, ip)
            if not cf:
                # decUnk1(3, 0): literal bytes
                count, ip = _get_code(ctx, src, ip, 3)
                count += 0 + 1
                ctx.datasize -= count
                while count > 0:
                    val, ip = _get_code(ctx, src, ip, 8)
                    dst[op] = val & 0xFF
                    op -= 1
                    count -= 1
            else:
                # decUnk2(8): back-reference with size=1
                offset, ip = _get_code(ctx, src, ip, 8)
                count = ctx.size + 1
                ctx.datasize -= count
                while count > 0:
                    dst[op] = dst[op + offset] if (op + offset) < len(dst) else 0
                    op -= 1
                    count -= 1
        else:
            c, ip = _get_code(ctx, src, ip, 2)
            if c == 3:
                # decUnk1(8, 8): literal bytes (longer)
                count, ip = _get_code(ctx, src, ip, 8)
                count += 8 + 1
                ctx.datasize -= count
                while count > 0:
                    val, ip = _get_code(ctx, src, ip, 8)
                    dst[op] = val & 0xFF
                    op -= 1
                    count -= 1
            elif c < 2:
                # decUnk2(c+9): back-reference
                ctx.size = c + 2
                offset, ip = _get_code(ctx, src, ip, c + 9)
                count = ctx.size + 1
                ctx.datasize -= count
                while count > 0:
                    dst[op] = dst[op + offset] if (op + offset) < len(dst) else 0
                    op -= 1
                    count -= 1
            else:
                # c == 2: decUnk2(12) with variable size
                ctx.size, ip = _get_code(ctx, src, ip, 8)
                offset, ip = _get_code(ctx, src, ip, 12)
                count = ctx.size + 1
                ctx.datasize -= count
                while count > 0:
                    dst[op] = dst[op + offset] if (op + offset) < len(dst) else 0
                    op -= 1
                    count -= 1

    if ctx.crc != 0:
        return None  # CRC mismatch

    return dst


class _UnpackCtx:
    __slots__ = ("size", "crc", "chk", "datasize")

    def __init__(self):
        self.size = 0
        self.crc = 0
        self.chk = 0
        self.datasize = 0


def _read_be_u32(data, offset):
    """Read big-endian uint32 from data at offset."""
    return (data[offset] << 24) | (data[offset + 1] << 16) | \
           (data[offset + 2] << 8) | data[offset + 3]


def _rcr(ctx, cf):
    """Rotate carry right: shift chk right by 1, inject cf into MSB.

    Returns the bit that was shifted out (the old LSB).
    """
    r_cf = (ctx.chk & 1) != 0
    ctx.chk >>= 1
    if cf:
        ctx.chk |= 0x80000000
    return r_cf


def _next_chunk(ctx, src, ip):
    """Get the next bit from the bit stream.

    When the accumulator (chk) is exhausted, refill from source.
    Returns (bit_value, updated_ip).
    """
    cf = _rcr(ctx, False)
    if ctx.chk == 0:
        ctx.chk = _read_be_u32(src, ip)
        ip -= 4
        ctx.crc ^= ctx.chk
        cf = _rcr(ctx, True)
    return cf, ip


def _get_code(ctx, src, ip, num_bits):
    """Read num_bits from the bit stream, MSB first.

    Returns (value, updated_ip).
    """
    c = 0
    for _ in range(num_bits):
        c <<= 1
        cf, ip = _next_chunk(ctx, src, ip)
        if cf:
            c |= 1
    return c, ip
