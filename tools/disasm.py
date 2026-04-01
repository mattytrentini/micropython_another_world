"""Another World bytecode disassembler.

Usage:
    micropython disasm.py <bytecode_file>
    python3 disasm.py <bytecode_file>

Reads a raw bytecode file and prints human-readable assembly.
"""

import sys
sys.path.insert(0, ".")

from aw.consts import OPCODE_NAMES


class Disassembler:
    def __init__(self, code):
        self.code = memoryview(bytearray(code))
        self.pc = 0

    def _byte(self):
        v = self.code[self.pc]
        self.pc += 1
        return v

    def _word(self):
        pc = self.pc
        v = (self.code[pc] << 8) | self.code[pc + 1]
        self.pc = pc + 2
        return v

    def _sword(self):
        v = self._word()
        return v - 0x10000 if v >= 0x8000 else v

    def disasm_one(self):
        """Disassemble one instruction. Returns (addr, text) or None at end."""
        if self.pc >= len(self.code):
            return None

        addr = self.pc
        op = self._byte()

        if op & 0x80:
            off = ((op << 8) | self._byte()) * 2
            off &= 0xFFFE
            x = self._byte()
            y = self._byte()
            return (addr, "drawPolySimple  off=0x{:04X} x={} y={}".format(off, x, y))

        if op & 0x40:
            off = self._word() * 2
            x_raw = self._byte()
            parts = ["off=0x{:04X}".format(off)]

            if not (op & 0x20):
                if not (op & 0x10):
                    x2 = self._byte()
                    parts.append("x=0x{:04X}".format((x_raw << 8) | x2))
                else:
                    parts.append("x=var[0x{:02X}]".format(x_raw))
            else:
                if op & 0x10:
                    parts.append("x={}+0x100".format(x_raw))
                else:
                    parts.append("x={}".format(x_raw))

            y_raw = self._byte()
            if not (op & 0x08):
                if not (op & 0x04):
                    y2 = self._byte()
                    parts.append("y=0x{:04X}".format((y_raw << 8) | y2))
                else:
                    parts.append("y=var[0x{:02X}]".format(y_raw))
            else:
                parts.append("y={}".format(y_raw))

            z_raw = self._byte()
            if not (op & 0x02):
                if not (op & 0x01):
                    self.pc -= 1
                    parts.append("zoom=64")
                else:
                    parts.append("zoom=var[0x{:02X}]".format(z_raw))
            else:
                if op & 0x01:
                    self.pc -= 1
                    parts.append("zoom=64 seg=video2")
                else:
                    parts.append("zoom={}".format(z_raw))

            return (addr, "drawPolyComplex " + " ".join(parts))

        if op > 0x1A:
            return (addr, "??? 0x{:02X}".format(op))

        name = OPCODE_NAMES[op]

        if op == 0x00:  # movConst
            var = self._byte()
            val = self._sword()
            return (addr, "{:<20s} var[0x{:02X}] = {}".format(name, var, val))
        elif op == 0x01:  # mov
            dst = self._byte()
            src = self._byte()
            return (addr, "{:<20s} var[0x{:02X}] = var[0x{:02X}]".format(name, dst, src))
        elif op == 0x02:  # add
            dst = self._byte()
            src = self._byte()
            return (addr, "{:<20s} var[0x{:02X}] += var[0x{:02X}]".format(name, dst, src))
        elif op == 0x03:  # addConst
            var = self._byte()
            val = self._sword()
            return (addr, "{:<20s} var[0x{:02X}] += {}".format(name, var, val))
        elif op == 0x04:  # call
            offset = self._word()
            return (addr, "{:<20s} 0x{:04X}".format(name, offset))
        elif op == 0x05:  # ret
            return (addr, name)
        elif op == 0x06:  # yieldTask
            return (addr, name)
        elif op == 0x07:  # jmp
            offset = self._word()
            return (addr, "{:<20s} 0x{:04X}".format(name, offset))
        elif op == 0x08:  # installTask
            thread = self._byte()
            offset = self._word()
            return (addr, "{:<20s} thread={} pc=0x{:04X}".format(name, thread, offset))
        elif op == 0x09:  # jmpIfVar
            var = self._byte()
            offset = self._word()
            return (addr, "{:<20s} var[0x{:02X}]--, jnz 0x{:04X}".format(name, var, offset))
        elif op == 0x0A:  # condJmp
            return self._disasm_condjmp(addr, name)
        elif op == 0x0B:  # setPalette
            pal = self._word()
            return (addr, "{:<20s} palette={}".format(name, pal >> 8))
        elif op == 0x0C:  # changeTasksState
            start = self._byte()
            end = self._byte()
            state = self._byte()
            state_str = {0: "active", 1: "paused", 2: "kill"}.get(state, str(state))
            return (addr, "{:<20s} threads {}..{} -> {}".format(name, start, end, state_str))
        elif op == 0x0D:  # selectPage
            page = self._byte()
            return (addr, "{:<20s} page=0x{:02X}".format(name, page))
        elif op == 0x0E:  # fillPage
            page = self._byte()
            color = self._byte()
            return (addr, "{:<20s} page=0x{:02X} color={}".format(name, page, color))
        elif op == 0x0F:  # copyPage
            src = self._byte()
            dst = self._byte()
            return (addr, "{:<20s} src=0x{:02X} dst=0x{:02X}".format(name, src, dst))
        elif op == 0x10:  # updateDisplay
            page = self._byte()
            return (addr, "{:<20s} page=0x{:02X}".format(name, page))
        elif op == 0x11:  # removeTask
            return (addr, name)
        elif op == 0x12:  # drawString
            str_id = self._word()
            x = self._byte()
            y = self._byte()
            color = self._byte()
            return (addr, "{:<20s} str=0x{:04X} x={} y={} color={}".format(
                name, str_id, x, y, color))
        elif op == 0x13:  # sub
            dst = self._byte()
            src = self._byte()
            return (addr, "{:<20s} var[0x{:02X}] -= var[0x{:02X}]".format(name, dst, src))
        elif op in (0x14, 0x15, 0x16, 0x17):  # and, or, shl, shr
            var = self._byte()
            val = self._word()
            ops = {0x14: "&=", 0x15: "|=", 0x16: "<<=", 0x17: ">>="}
            return (addr, "{:<20s} var[0x{:02X}] {} 0x{:04X}".format(
                name, var, ops[op], val))
        elif op == 0x18:  # playSound
            res = self._word()
            freq = self._byte()
            vol = self._byte()
            ch = self._byte()
            return (addr, "{:<20s} res=0x{:04X} freq={} vol={} ch={}".format(
                name, res, freq, vol, ch))
        elif op == 0x19:  # updateResources
            res_id = self._word()
            return (addr, "{:<20s} res=0x{:04X}".format(name, res_id))
        elif op == 0x1A:  # playMusic
            res = self._word()
            delay = self._word()
            pos = self._byte()
            return (addr, "{:<20s} res=0x{:04X} delay={} pos={}".format(
                name, res, delay, pos))

        return (addr, "{} (unhandled)".format(name))

    def _disasm_condjmp(self, addr, name):
        op = self._byte()
        var = self._byte()

        if op & 0x80:
            rhs = "var[0x{:02X}]".format(self._byte())
        elif op & 0x40:
            rhs = str(self._sword())
        else:
            rhs = str(self._byte())

        cond_str = {0: "==", 1: "!=", 2: ">", 3: ">=", 4: "<", 5: "<="}.get(
            op & 7, "?{}")
        target = self._word()
        return (addr, "{:<20s} if var[0x{:02X}] {} {} goto 0x{:04X}".format(
            name, var, cond_str, rhs, target))

    def disasm_all(self):
        """Disassemble entire code buffer. Returns list of (addr, text)."""
        results = []
        while True:
            r = self.disasm_one()
            if r is None:
                break
            results.append(r)
        return results


def main():
    if len(sys.argv) < 2:
        print("Usage: {} <bytecode_file>".format(sys.argv[0]))
        sys.exit(1)

    with open(sys.argv[1], "rb") as f:
        code = f.read()

    d = Disassembler(code)
    for addr, text in d.disasm_all():
        print("{:04X}: {}".format(addr, text))


if __name__ == "__main__":
    main()
