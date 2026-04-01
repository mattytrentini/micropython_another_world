"""Unit tests for the Another World VM opcodes.

Tests each opcode with synthetic bytecode programs.
Run with: python3 -m pytest tests/test_vm_opcodes.py
      or: micropython tests/test_vm_opcodes.py
"""

import sys
import struct

sys.path.insert(0, ".")

from aw.vm import VM, _to_i16
from aw.consts import (
    THREAD_INACTIVE, THREAD_KILL,
    STATE_ACTIVE, STATE_PAUSED,
    VAR_SCROLL_Y, VAR_TIMER, VAR_PAUSE_SLICES,
)


def make_vm(code_bytes, regs=None):
    """Create a VM loaded with the given bytecode and optional initial registers.

    Appends a yieldTask (0x06) to stop execution after the test code.
    """
    code = bytearray(code_bytes) + bytearray([0x06])  # append yield
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    if regs:
        for k, v in regs.items():
            vm.regs[k] = v
    return vm


def run_vm(vm):
    """Run one frame of the VM (all active tasks)."""
    vm.run_tasks()
    return vm


# --- Helper ---

def test_to_i16():
    assert _to_i16(0) == 0
    assert _to_i16(1) == 1
    assert _to_i16(0x7FFF) == 32767
    assert _to_i16(0x8000) == -32768
    assert _to_i16(0xFFFF) == -1
    assert _to_i16(0x10000) == 0  # overflow wraps
    assert _to_i16(-1) == -1  # already negative, mask to 0xFFFF then convert


# --- Opcode tests ---

def test_op_mov_const():
    """0x00: var = val"""
    # movConst var[0x10] = 0x0042
    vm = run_vm(make_vm([0x00, 0x10, 0x00, 0x42]))
    assert vm.regs[0x10] == 0x42

    # Negative value: movConst var[0x20] = -1 (0xFFFF)
    vm = run_vm(make_vm([0x00, 0x20, 0xFF, 0xFF]))
    assert vm.regs[0x20] == -1


def test_op_mov():
    """0x01: dst = src"""
    vm = make_vm([0x01, 0x10, 0x20], regs={0x20: 123})
    run_vm(vm)
    assert vm.regs[0x10] == 123


def test_op_add():
    """0x02: dst += src"""
    vm = make_vm([0x02, 0x10, 0x20], regs={0x10: 10, 0x20: 20})
    run_vm(vm)
    assert vm.regs[0x10] == 30


def test_op_add_overflow():
    """0x02: dst += src with overflow"""
    vm = make_vm([0x02, 0x10, 0x20], regs={0x10: 32767, 0x20: 1})
    run_vm(vm)
    assert vm.regs[0x10] == -32768


def test_op_add_const():
    """0x03: var += val"""
    # addConst var[0x10] += 5
    vm = make_vm([0x03, 0x10, 0x00, 0x05], regs={0x10: 10})
    run_vm(vm)
    assert vm.regs[0x10] == 15

    # addConst with negative: var[0x10] += -3 (0xFFFD)
    vm = make_vm([0x03, 0x10, 0xFF, 0xFD], regs={0x10: 10})
    run_vm(vm)
    assert vm.regs[0x10] == 7


def test_op_call_ret():
    """0x04/0x05: call and return"""
    # call 0x0005 (address of movConst), then movConst + ret, then yield
    # PC layout:
    #   0x0000: call 0x0005
    #   0x0003: yield (appended by make_vm... but we manually build this)
    #   0x0005: movConst var[0x10] = 0x0042
    #   0x0009: ret
    code = bytearray([
        0x04, 0x00, 0x05,               # call 0x0005
        0x06,                             # yield (return point)
        0x00,                             # padding (unreachable)
        0x00, 0x10, 0x00, 0x42,          # movConst var[0x10] = 0x42
        0x05,                             # ret
    ])
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    vm.run_tasks()
    assert vm.regs[0x10] == 0x42


def test_op_yield_task():
    """0x06: pause current thread"""
    # Two movConst ops with yield between them
    code = bytearray([
        0x00, 0x10, 0x00, 0x01,  # movConst var[0x10] = 1
        0x06,                     # yield
        0x00, 0x20, 0x00, 0x02,  # movConst var[0x20] = 2
        0x06,                     # yield
    ])
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE

    # First frame: executes first movConst, then yields
    vm.run_tasks()
    assert vm.regs[0x10] == 1
    assert vm.regs[0x20] == 0  # not yet executed

    # Second frame: executes second movConst
    vm.run_tasks()
    assert vm.regs[0x20] == 2


def test_op_jmp():
    """0x07: unconditional jump"""
    # jmp to address 0x05 (skip the first movConst after jmp)
    code = bytearray([
        0x07, 0x00, 0x07,              # jmp 0x0007
        0x00, 0x10, 0x00, 0x01,        # movConst var[0x10] = 1 (skipped)
        0x00, 0x20, 0x00, 0x02,        # movConst var[0x20] = 2
        0x06,                            # yield
    ])
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    vm.run_tasks()
    assert vm.regs[0x10] == 0  # skipped
    assert vm.regs[0x20] == 2  # executed


def test_op_install_task():
    """0x08: set thread PC for next frame"""
    # installTask thread=1, pc=0x0000 (some offset)
    code = bytearray([
        0x08, 0x01, 0x00, 0x00,  # installTask thread=1, offset=0
        0x06,                     # yield
    ])
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    vm.run_tasks()
    # Requested PC for thread 1 should be set
    assert vm.task_pc[1][1] == 0x0000


def test_op_jmp_if_var():
    """0x09: var--; if var != 0 then jmp"""
    # Loop 3 times: jmpIfVar var[0x10] to start, accumulate in var[0x20]
    code = bytearray([
        0x03, 0x20, 0x00, 0x01,    # addConst var[0x20] += 1
        0x09, 0x10, 0x00, 0x00,    # jmpIfVar var[0x10], goto 0x0000
        0x06,                       # yield
    ])
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    vm.regs[0x10] = 3
    vm.run_tasks()
    assert vm.regs[0x20] == 3  # looped 3 times
    assert vm.regs[0x10] == 0  # decremented to 0


def test_op_cond_jmp_eq():
    """0x0A: conditional jump - equal"""
    # condJmp: if var[0x10] == 42 goto target
    code = bytearray([
        0x0A, 0x00, 0x10, 42,       # condJmp op=0x00(eq, byte literal), var=0x10, val=42
        0x00, 0x0A,                  # target=0x000A
        0x00, 0x20, 0x00, 0x01,     # movConst var[0x20] = 1 (skipped if jump taken)
        # 0x000A:
        0x06,                        # yield
    ])
    # Test: condition true
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    vm.regs[0x10] = 42
    vm.run_tasks()
    assert vm.regs[0x20] == 0  # skipped (jump taken)

    # Test: condition false
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    vm.regs[0x10] = 41
    vm.run_tasks()
    assert vm.regs[0x20] == 1  # not skipped


def test_op_cond_jmp_ne():
    """0x0A: conditional jump - not equal"""
    code = bytearray([
        0x0A, 0x01, 0x10, 42,       # condJmp op=0x01(ne), var=0x10, val=42
        0x00, 0x0A,                  # target
        0x00, 0x20, 0x00, 0x01,     # movConst var[0x20] = 1
        0x06,
    ])
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    vm.regs[0x10] = 41  # != 42
    vm.run_tasks()
    assert vm.regs[0x20] == 0  # jump taken


def test_op_cond_jmp_gt():
    """0x0A: conditional jump - greater than"""
    code = bytearray([
        0x0A, 0x02, 0x10, 10,       # condJmp op=0x02(gt), var=0x10, val=10
        0x00, 0x0A,                  # target
        0x00, 0x20, 0x00, 0x01,     # movConst var[0x20] = 1
        0x06,
    ])
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    vm.regs[0x10] = 11
    vm.run_tasks()
    assert vm.regs[0x20] == 0  # jump taken (11 > 10)


def test_op_cond_jmp_with_reg():
    """0x0A: conditional jump with register operand"""
    code = bytearray([
        0x0A, 0x80, 0x10, 0x20,     # condJmp op=0x80(eq, from reg), var=0x10, rhs=var[0x20]
        0x00, 0x0A,                  # target
        0x00, 0x30, 0x00, 0x01,     # movConst var[0x30] = 1
        0x06,
    ])
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    vm.regs[0x10] = 99
    vm.regs[0x20] = 99
    vm.run_tasks()
    assert vm.regs[0x30] == 0  # jump taken (99 == 99)


def test_op_cond_jmp_with_word():
    """0x0A: conditional jump with 16-bit signed literal"""
    code = bytearray([
        0x0A, 0x40, 0x10, 0x01, 0x00,  # condJmp op=0x40(eq, word), var=0x10, val=256
        0x00, 0x0B,                      # target
        0x00, 0x20, 0x00, 0x01,         # movConst var[0x20] = 1
        0x06,
    ])
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    vm.regs[0x10] = 256
    vm.run_tasks()
    assert vm.regs[0x20] == 0  # jump taken


def test_op_change_tasks_state_pause():
    """0x0C: batch set thread states to paused"""
    code = bytearray([
        0x0C, 0x01, 0x03, 0x01,  # changeTasksState start=1, end=3, state=1(paused)
        0x06,
    ])
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    vm.run_tasks()
    for i in range(1, 4):
        assert vm.task_state[1][i] == STATE_PAUSED


def test_op_change_tasks_state_kill():
    """0x0C: batch kill threads"""
    code = bytearray([
        0x0C, 0x02, 0x04, 0x02,  # changeTasksState start=2, end=4, state=2(kill)
        0x06,
    ])
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    vm.run_tasks()
    for i in range(2, 5):
        assert vm.task_pc[1][i] == THREAD_KILL


def test_op_remove_task():
    """0x11: kill current thread"""
    code = bytearray([
        0x00, 0x10, 0x00, 0x01,  # movConst var[0x10] = 1
        0x11,                     # removeTask
        0x00, 0x20, 0x00, 0x02,  # movConst var[0x20] = 2 (never reached)
        0x06,
    ])
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    vm.run_tasks()
    assert vm.regs[0x10] == 1
    assert vm.regs[0x20] == 0  # never executed
    assert vm.task_pc[0][0] == THREAD_INACTIVE


def test_op_sub():
    """0x13: dst -= src"""
    vm = make_vm([0x13, 0x10, 0x20], regs={0x10: 50, 0x20: 30})
    run_vm(vm)
    assert vm.regs[0x10] == 20


def test_op_and():
    """0x14: var &= mask"""
    vm = make_vm([0x14, 0x10, 0x0F, 0x0F], regs={0x10: 0x1234})
    run_vm(vm)
    assert vm.regs[0x10] == _to_i16(0x1234 & 0x0F0F)


def test_op_or():
    """0x15: var |= val"""
    vm = make_vm([0x15, 0x10, 0xF0, 0x00], regs={0x10: 0x0F})
    run_vm(vm)
    assert vm.regs[0x10] == _to_i16(0x0F | 0xF000)


def test_op_shl():
    """0x16: var <<= n"""
    vm = make_vm([0x16, 0x10, 0x00, 0x04], regs={0x10: 1})
    run_vm(vm)
    assert vm.regs[0x10] == 16


def test_op_shr():
    """0x17: var >>= n"""
    vm = make_vm([0x17, 0x10, 0x00, 0x04], regs={0x10: 256})
    run_vm(vm)
    assert vm.regs[0x10] == 16


def test_op_play_sound_stub():
    """0x18: playSound (stub, just verify bytes consumed)"""
    vm = make_vm([0x18, 0x00, 0x5B, 0x01, 0x40, 0x01])
    run_vm(vm)
    # No crash = bytes consumed correctly


def test_op_update_resources_stub():
    """0x19: updateResources (stub, just verify bytes consumed)"""
    vm = make_vm([0x19, 0x00, 0x00])
    run_vm(vm)


def test_op_play_music_stub():
    """0x1A: playMusic (stub, just verify bytes consumed)"""
    vm = make_vm([0x1A, 0x00, 0x01, 0x00, 0x10, 0x00])
    run_vm(vm)


def test_op_set_palette_stub():
    """0x0B: setPalette (stub, verify bytes consumed)"""
    vm = make_vm([0x0B, 0x03, 0x00])
    run_vm(vm)


def test_op_select_page_stub():
    """0x0D: selectPage (stub, verify bytes consumed)"""
    vm = make_vm([0x0D, 0x01])
    run_vm(vm)


def test_op_fill_page_stub():
    """0x0E: fillPage (stub, verify bytes consumed)"""
    vm = make_vm([0x0E, 0x01, 0x00])
    run_vm(vm)


def test_op_copy_page_stub():
    """0x0F: copyPage (stub, verify bytes consumed)"""
    vm = make_vm([0x0F, 0x01, 0x02])
    run_vm(vm)


def test_op_update_display_stub():
    """0x10: updateDisplay (does NOT yield, continues executing)"""
    code = bytearray([
        0x00, 0x10, 0x00, 0x01,  # movConst var[0x10] = 1
        0x10, 0xFF,               # updateDisplay page=0xFF
        0x00, 0x20, 0x00, 0x02,  # movConst var[0x20] = 2
        0x06,                     # yieldTask
    ])
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    vm.run_tasks()
    assert vm.regs[0x10] == 1
    assert vm.regs[0x20] == 2  # updateDisplay does NOT yield
    assert vm.regs[VAR_TIMER] == 0


def test_op_draw_string_stub():
    """0x12: drawString (stub, verify bytes consumed)"""
    vm = make_vm([0x12, 0x00, 0x01, 0x14, 0x64, 0x0F])
    run_vm(vm)


def test_setup_tasks():
    """Test double-buffered task state management."""
    vm = VM()
    vm.set_code(bytearray([0x06]))  # just yield

    # Set up thread 0 as active
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE

    # Request: install thread 5 at PC 0x100
    vm.task_pc[1][5] = 0x100
    vm.task_state[1][5] = STATE_ACTIVE

    vm.setup_tasks()

    # Thread 5 should now be installed in current bank
    assert vm.task_pc[0][5] == 0x100
    # Requested bank should be cleared
    assert vm.task_pc[1][5] == THREAD_INACTIVE


def test_setup_tasks_kill():
    """Test that THREAD_KILL deactivates a thread."""
    vm = VM()
    vm.set_code(bytearray([0x06]))

    vm.task_pc[0][3] = 0x50
    vm.task_state[0][3] = STATE_ACTIVE
    vm.task_pc[1][3] = THREAD_KILL

    vm.setup_tasks()

    assert vm.task_pc[0][3] == THREAD_INACTIVE


def test_multi_thread():
    """Test multiple threads executing in the same frame."""
    # Thread 0 sets var[0x10] = 1, thread 1 sets var[0x20] = 2
    code = bytearray([
        # Thread 0 starts at 0x0000:
        0x00, 0x10, 0x00, 0x01,  # movConst var[0x10] = 1
        0x06,                     # yield
        # Thread 1 starts at 0x0005:
        0x00, 0x20, 0x00, 0x02,  # movConst var[0x20] = 2
        0x06,                     # yield
    ])
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    vm.task_pc[0][1] = 5
    vm.task_state[0][1] = STATE_ACTIVE

    vm.run_tasks()
    assert vm.regs[0x10] == 1
    assert vm.regs[0x20] == 2


def test_draw_poly_simple_stub():
    """Test 0x80-prefix polygon draw consumes correct bytes."""
    # Opcode 0x80 | some_bits, then 3 more bytes (lo_off, x, y)
    code = bytearray([
        0x80, 0x10, 0x50, 0x60,  # drawPolySimple: off=(0x80<<8|0x10)*2, x=0x50, y=0x60
        0x06,
    ])
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    vm.run_tasks()
    # No crash = correct byte count consumed


def test_draw_poly_complex_stub_default_zoom():
    """Test 0x40-prefix polygon draw with default zoom (no zoom byte consumed)."""
    # op=0x40 (bits 5-0 all clear: x=16bit, y=16bit, zoom=default)
    code = bytearray([
        0x40,                    # op: x=16bit, y=16bit, zoom=64 default
        0x00, 0x10,              # offset word
        0x00, 0x50,              # x = 0x0050
        0x00, 0x60,              # y = 0x0060
        # zoom byte is fetched then PC backed up (not consumed)
        0x06,                    # yield (this byte is peeked as zoom then un-consumed)
    ])
    vm = VM()
    vm.set_code(code)
    vm.task_pc[0][0] = 0
    vm.task_state[0][0] = STATE_ACTIVE
    vm.run_tasks()
    # If byte consumption is wrong, we'll get a bad opcode error


# --- Run all tests ---

def run_tests():
    """Simple test runner for MicroPython (no pytest needed)."""
    import gc
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    for t in tests:
        name = t.__name__
        try:
            t()
            passed += 1
            print("  PASS: {}".format(name))
        except Exception as e:
            failed += 1
            print("  FAIL: {} - {}".format(name, e))
        gc.collect()

    print("\n{} passed, {} failed out of {} tests".format(passed, failed, passed + failed))
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
