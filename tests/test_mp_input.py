"""Test input reading on MicroPython.

Run: mpunix micropython tests/test_mp_input.py
Press some keys, then q to quit. Shows what the input system detects.
"""
import sys
sys.path.insert(0, ".")

import time

# Test 1: raw read capability
print("=== Input Diagnostics ===")
print()

import select
print("select.poll:", hasattr(select, "poll"))

import termios, tty
old = termios.tcgetattr(0)
tty.setcbreak(0)
print("cbreak mode set")

p = select.poll()
p.register(sys.stdin, select.POLLIN)

# Test 2: check if buffer.read works
print()
print("Press a key...")
result = p.poll(5000)
if result:
    print("poll: data ready")
    try:
        ch = sys.stdin.buffer.read(1)
        print("buffer.read(1):", repr(ch))
    except Exception as e:
        print("buffer.read failed:", e)
        try:
            ch = sys.stdin.read(1)
            print("stdin.read(1):", repr(ch))
        except Exception as e2:
            print("stdin.read also failed:", e2)
else:
    print("poll: timeout, no input")

# Test 3: continuous polling like the game does
print()
print("Now testing continuous poll loop (press keys, q to quit)...")
print()

while True:
    events = p.poll(100)
    if events:
        try:
            ch = sys.stdin.buffer.read(1)
        except:
            ch = sys.stdin.read(1)
            if isinstance(ch, str):
                ch = ch.encode()
        print("  got:", repr(ch))
        if ch == b'q':
            break
    else:
        pass  # no input, keep looping

termios.tcsetattr(0, termios.TCSADRAIN, old)
print("Done")
