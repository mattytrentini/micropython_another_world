"""Another World bytecode virtual machine.

Implements the 27-opcode instruction set plus 2 polygon-draw pseudo-opcodes,
with a 64-thread cooperative scheduler and double-buffered task state.
"""

import array
import struct

from .consts import (
    NUM_THREADS, NUM_VARIABLES, CALL_STACK_DEPTH,
    THREAD_INACTIVE, THREAD_KILL, STATE_ACTIVE, STATE_PAUSED,
    VAR_RANDOM_SEED, VAR_SCROLL_Y, VAR_PAUSE_SLICES, VAR_TIMER,
    VAR_HERO_ACTION, VAR_HERO_POS_UP_DOWN, VAR_HERO_POS_JUMP_DOWN,
    VAR_HERO_POS_LEFT_RIGHT, VAR_HERO_POS_MASK, VAR_HERO_ACTION_POS_MASK,
)


def _to_i16(val):
    """Convert an integer to signed 16-bit (handles overflow)."""
    val &= 0xFFFF
    return val - 0x10000 if val >= 0x8000 else val


class VM:
    """Another World bytecode interpreter with cooperative thread scheduler."""

    def __init__(self):
        # 256 x 16-bit signed registers
        self.regs = array.array("h", (0 for _ in range(NUM_VARIABLES)))

        # Thread PC offsets: [0]=current, [1]=requested for next frame
        # Stored as flat arrays of 16-bit unsigned values
        self.task_pc = [
            array.array("H", (THREAD_INACTIVE for _ in range(NUM_THREADS))),
            array.array("H", (THREAD_INACTIVE for _ in range(NUM_THREADS))),
        ]
        # Thread states: [0]=current, [1]=requested
        self.task_state = [
            bytearray(NUM_THREADS),
            bytearray(NUM_THREADS),
        ]

        # Call stack (shared, reset per thread execution)
        self.call_stack = array.array("H", (0 for _ in range(CALL_STACK_DEPTH)))
        self.stack_ptr = 0

        # Execution state
        self._code = None       # memoryview into seg_code
        self._pc = 0            # current PC offset
        self._paused = False    # set by yield/remove/updateDisplay

        # Callbacks set by engine (video, resource, etc.)
        self.video = None
        self.resource = None
        self.mixer = None

        # Build opcode dispatch table
        self._optable = (
            self._op_mov_const,         # 0x00
            self._op_mov,               # 0x01
            self._op_add,               # 0x02
            self._op_add_const,         # 0x03
            self._op_call,              # 0x04
            self._op_ret,               # 0x05
            self._op_yield_task,        # 0x06
            self._op_jmp,               # 0x07
            self._op_install_task,      # 0x08
            self._op_jmp_if_var,        # 0x09
            self._op_cond_jmp,          # 0x0A
            self._op_set_palette,       # 0x0B
            self._op_change_tasks_state,  # 0x0C
            self._op_select_page,       # 0x0D
            self._op_fill_page,         # 0x0E
            self._op_copy_page,         # 0x0F
            self._op_update_display,    # 0x10
            self._op_remove_task,       # 0x11
            self._op_draw_string,       # 0x12
            self._op_sub,               # 0x13
            self._op_and,               # 0x14
            self._op_or,                # 0x15
            self._op_shl,               # 0x16
            self._op_shr,               # 0x17
            self._op_play_sound,        # 0x18
            self._op_update_resources,  # 0x19
            self._op_play_music,        # 0x1A
        )

    def restart_at(self, part_id):
        """Initialize VM state and start executing a game part."""
        # Clear all registers
        for i in range(NUM_VARIABLES):
            self.regs[i] = 0

        # Initialize random seed
        self.regs[VAR_RANDOM_SEED] = 0x1234  # deterministic seed

        # Deactivate all threads
        for i in range(NUM_THREADS):
            self.task_pc[0][i] = THREAD_INACTIVE
            self.task_pc[1][i] = THREAD_INACTIVE
            self.task_state[0][i] = STATE_PAUSED
            self.task_state[1][i] = STATE_PAUSED

        # Thread 0 starts at offset 0
        self.task_pc[0][0] = 0
        self.task_state[0][0] = STATE_ACTIVE

    def set_code(self, code_data):
        """Set the bytecode segment for execution.

        Args:
            code_data: bytearray containing the bytecode.
        """
        self._code = memoryview(code_data)

    def setup_tasks(self):
        """Copy requested state from bank[1] to bank[0] for next frame."""
        pc0 = self.task_pc[0]
        pc1 = self.task_pc[1]
        st0 = self.task_state[0]
        st1 = self.task_state[1]

        for i in range(NUM_THREADS):
            req_pc = pc1[i]
            if req_pc != THREAD_INACTIVE:
                # Apply requested PC change
                if req_pc == THREAD_KILL:
                    pc0[i] = THREAD_INACTIVE
                else:
                    pc0[i] = req_pc
                pc1[i] = THREAD_INACTIVE

            # Always copy requested state
            st0[i] = st1[i]

    def run_tasks(self):
        """Execute all active threads for one frame."""
        for i in range(NUM_THREADS):
            if self.task_state[0][i] != STATE_ACTIVE:
                continue

            pc = self.task_pc[0][i]
            if pc == THREAD_INACTIVE:
                continue

            self._pc = pc
            self.stack_ptr = 0
            self._paused = False
            self._execute()

            # Save PC back (may be 0xFFFF if thread was removed)
            self.task_pc[0][i] = self._pc & 0xFFFF

    def _execute(self):
        """Execute bytecode for the current thread until paused."""
        code = self._code
        while not self._paused:
            op = code[self._pc]
            self._pc += 1

            if op & 0x80:
                self._draw_poly_simple(op, code)
            elif op & 0x40:
                self._draw_poly_complex(op, code)
            elif op <= 0x1A:
                self._optable[op]()
            else:
                raise RuntimeError("bad opcode 0x{:02X} at pc={}".format(
                    op, self._pc - 1))

    # --- Fetch helpers (inlined for speed where possible) ---

    def _fetch_byte(self):
        """Fetch unsigned byte from code, advance PC."""
        v = self._code[self._pc]
        self._pc += 1
        return v

    def _fetch_word(self):
        """Fetch big-endian unsigned 16-bit word from code, advance PC."""
        pc = self._pc
        v = (self._code[pc] << 8) | self._code[pc + 1]
        self._pc = pc + 2
        return v

    def _fetch_sword(self):
        """Fetch big-endian signed 16-bit word from code, advance PC."""
        v = self._fetch_word()
        return v - 0x10000 if v >= 0x8000 else v

    # --- Standard opcodes (0x00 - 0x1A) ---

    def _op_mov_const(self):
        """0x00: var = val (16-bit signed)"""
        var = self._fetch_byte()
        val = self._fetch_sword()
        self.regs[var] = val

    def _op_mov(self):
        """0x01: dst = src"""
        dst = self._fetch_byte()
        src = self._fetch_byte()
        self.regs[dst] = self.regs[src]

    def _op_add(self):
        """0x02: dst += src"""
        dst = self._fetch_byte()
        src = self._fetch_byte()
        self.regs[dst] = _to_i16(self.regs[dst] + self.regs[src])

    def _op_add_const(self):
        """0x03: var += val (16-bit signed)"""
        var = self._fetch_byte()
        val = self._fetch_sword()
        self.regs[var] = _to_i16(self.regs[var] + val)

    def _op_call(self):
        """0x04: push PC, jump to offset"""
        offset = self._fetch_word()
        sp = self.stack_ptr
        if sp >= CALL_STACK_DEPTH:
            raise RuntimeError("call stack overflow")
        self.call_stack[sp] = self._pc
        self.stack_ptr = sp + 1
        self._pc = offset

    def _op_ret(self):
        """0x05: pop PC from stack"""
        if self.stack_ptr == 0:
            raise RuntimeError("call stack underflow")
        self.stack_ptr -= 1
        self._pc = self.call_stack[self.stack_ptr]

    def _op_yield_task(self):
        """0x06: pause current thread (yield to next)"""
        self._paused = True

    def _op_jmp(self):
        """0x07: unconditional jump"""
        self._pc = self._fetch_word()

    def _op_install_task(self):
        """0x08: set thread PC for next frame"""
        thread_id = self._fetch_byte()
        offset = self._fetch_word()
        self.task_pc[1][thread_id] = offset

    def _op_jmp_if_var(self):
        """0x09: var--; if var != 0 then jmp(offset)"""
        var = self._fetch_byte()
        self.regs[var] = _to_i16(self.regs[var] - 1)
        if self.regs[var] != 0:
            self._pc = self._fetch_word()
        else:
            self._fetch_word()  # skip target

    def _op_cond_jmp(self):
        """0x0A: conditional jump with multiple comparison modes"""
        op = self._fetch_byte()
        var = self._fetch_byte()
        b = self.regs[var]

        # Right operand encoding
        if op & 0x80:
            a = self.regs[self._fetch_byte()]
        elif op & 0x40:
            a = self._fetch_sword()
        else:
            a = self._fetch_byte()  # unsigned byte

        # Condition (low 3 bits)
        cond = op & 7
        if cond == 0:
            expr = (b == a)
        elif cond == 1:
            expr = (b != a)
        elif cond == 2:
            expr = (b > a)
        elif cond == 3:
            expr = (b >= a)
        elif cond == 4:
            expr = (b < a)
        elif cond == 5:
            expr = (b <= a)
        else:
            expr = False

        if expr:
            self._pc = self._fetch_word()
        else:
            self._fetch_word()  # skip target

    def _op_set_palette(self):
        """0x0B: request palette change"""
        pal_id = self._fetch_word()
        if self.video:
            self.video.set_palette_request(pal_id >> 8)

    def _op_change_tasks_state(self):
        """0x0C: batch set thread states"""
        start = self._fetch_byte()
        end = self._fetch_byte()
        end = end & (NUM_THREADS - 1)
        state = self._fetch_byte()

        if start > end:
            return

        if state == 2:
            # Kill threads
            for i in range(start, end + 1):
                self.task_pc[1][i] = THREAD_KILL
        elif state < 2:
            # Set active/paused
            for i in range(start, end + 1):
                self.task_state[1][i] = state

    def _op_select_page(self):
        """0x0D: set active drawing page"""
        page_id = self._fetch_byte()
        if self.video:
            self.video.select_page(page_id)

    def _op_fill_page(self):
        """0x0E: fill page with solid color"""
        page_id = self._fetch_byte()
        color = self._fetch_byte()
        if self.video:
            self.video.fill_page(page_id, color)

    def _op_copy_page(self):
        """0x0F: copy page (with optional scroll)"""
        src = self._fetch_byte()
        dst = self._fetch_byte()
        if self.video:
            self.video.copy_page(src, dst, self.regs[VAR_SCROLL_Y])

    def _op_update_display(self):
        """0x10: blit to screen, handle timing, yield"""
        page_id = self._fetch_byte()
        # Frame timing and display update handled by engine callback
        if self.video:
            self.video.update_display(page_id)
        self.regs[VAR_TIMER] = 0
        self._paused = True

    def _op_remove_task(self):
        """0x11: kill current thread"""
        self._pc = THREAD_INACTIVE
        self._paused = True

    def _op_draw_string(self):
        """0x12: draw text string"""
        str_id = self._fetch_word()
        x = self._fetch_byte()
        y = self._fetch_byte()
        color = self._fetch_byte()
        if self.video:
            self.video.draw_string(str_id, x, y, color)

    def _op_sub(self):
        """0x13: dst -= src"""
        dst = self._fetch_byte()
        src = self._fetch_byte()
        self.regs[dst] = _to_i16(self.regs[dst] - self.regs[src])

    def _op_and(self):
        """0x14: var &= mask (unsigned)"""
        var = self._fetch_byte()
        mask = self._fetch_word()
        self.regs[var] = _to_i16(self.regs[var] & mask)

    def _op_or(self):
        """0x15: var |= val (unsigned)"""
        var = self._fetch_byte()
        val = self._fetch_word()
        self.regs[var] = _to_i16(self.regs[var] | val)

    def _op_shl(self):
        """0x16: var <<= n (unsigned)"""
        var = self._fetch_byte()
        n = self._fetch_word()
        self.regs[var] = _to_i16((self.regs[var] & 0xFFFF) << n)

    def _op_shr(self):
        """0x17: var >>= n (unsigned)"""
        var = self._fetch_byte()
        n = self._fetch_word()
        self.regs[var] = _to_i16((self.regs[var] & 0xFFFF) >> n)

    def _op_play_sound(self):
        """0x18: play sound effect"""
        res_id = self._fetch_word()
        freq = self._fetch_byte()
        vol = self._fetch_byte()
        channel = self._fetch_byte()
        if self.mixer:
            self.mixer.play_sound(res_id, freq, vol, channel)

    def _op_update_resources(self):
        """0x19: load resource or invalidate all"""
        res_id = self._fetch_word()
        if self.resource:
            if res_id == 0:
                self.resource.invalidate_all()
            else:
                self.resource.load_or_setup_part(res_id)

    def _op_play_music(self):
        """0x1A: play/stop music"""
        res_num = self._fetch_word()
        delay = self._fetch_word()
        pos = self._fetch_byte()
        if self.mixer:
            self.mixer.play_music(res_num, delay, pos)

    # --- Polygon draw pseudo-opcodes ---

    def _draw_poly_simple(self, op, code):
        """Handle 0x80 prefix: simple cinematic polygon draw.

        Encoding: opcode byte has bit 7 set.
        off = ((opcode << 8) | nextByte) * 2
        x = nextByte, y = nextByte
        if y > 199: y=199, x+=overflow
        """
        off = ((op << 8) | self._fetch_byte()) * 2
        off &= 0xFFFE  # mask off the high bit from opcode
        x = self._fetch_byte()
        y = self._fetch_byte()
        h = y - 199
        if h > 0:
            y = 199
            x += h
        if self.video:
            self.video.draw_shape_at(off, x, y, 0xFF, 64, False)

    def _draw_poly_complex(self, op, code):
        """Handle 0x40 prefix: complex polygon draw with variable parameters.

        Bits 5-0 of the opcode encode how x, y, zoom are sourced.
        """
        off = self._fetch_word() * 2
        x = self._fetch_byte()
        use_seg_video2 = False

        # X encoding (bits 5,4)
        if not (op & 0x20):
            if not (op & 0x10):
                x = (x << 8) | self._fetch_byte()
            else:
                x = self.regs[x]
        else:
            if op & 0x10:
                x += 0x100

        # Y encoding (bits 3,2)
        y = self._fetch_byte()
        if not (op & 0x08):
            if not (op & 0x04):
                y = (y << 8) | self._fetch_byte()
            else:
                y = self.regs[y]

        # Zoom encoding (bits 1,0)
        zoom = self._fetch_byte()
        if not (op & 0x02):
            if not (op & 0x01):
                # No zoom param consumed, put byte back
                self._pc -= 1
                zoom = 64
            else:
                zoom = self.regs[zoom]
        else:
            if op & 0x01:
                use_seg_video2 = True
                self._pc -= 1
                zoom = 64
            # else: zoom = literal byte already fetched

        if self.video:
            self.video.draw_shape_at(off, x, y, 0xFF, zoom, use_seg_video2)

    # --- Input handling ---

    def update_input(self, input_state):
        """Map input state to VM registers."""
        lr = 0
        ud = 0
        jd = 0
        action = 0

        if input_state.right:
            lr = 1
        elif input_state.left:
            lr = -1

        if input_state.down:
            ud = 1
            jd = 1
        elif input_state.up:
            ud = -1
            jd = -1

        if input_state.action:
            action = 1

        self.regs[VAR_HERO_POS_LEFT_RIGHT] = lr
        self.regs[VAR_HERO_POS_UP_DOWN] = ud
        self.regs[VAR_HERO_POS_JUMP_DOWN] = jd
        self.regs[VAR_HERO_ACTION] = action

        mask = 0
        if input_state.right:
            mask |= 1
        if input_state.left:
            mask |= 2
        if input_state.down:
            mask |= 4
        if input_state.up:
            mask |= 8
        self.regs[VAR_HERO_POS_MASK] = mask

        action_mask = mask
        if input_state.action:
            action_mask |= 0x80
        self.regs[VAR_HERO_ACTION_POS_MASK] = action_mask
