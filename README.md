# Another World - MicroPython

A port of Eric Chahi's **Another World** (1991) game engine to MicroPython, with a hardware-agnostic design targeting the MicroPython unix port, RP2040/RP2350, and ESP32-S3.

The engine implements the original bytecode virtual machine, polygon renderer, and resource system. It runs the real game data — the full intro cinematic, all levels, and gameplay.

![Intro frame](https://raw.githubusercontent.com/mattytrentini/micropython_another_world/main/docs/intro.png)

## How It Works

Another World is built on a custom bytecode VM with 27 opcodes, a 64-thread cooperative scheduler, and a polygon-based renderer (not sprites). This project reimplements that VM in pure Python, targeting MicroPython compatibility.

Key subsystems:
- **Bytecode VM** (`aw/vm.py`): 27 opcodes + 2 polygon draw pseudo-opcodes, 64 cooperative threads
- **Polygon renderer** (`aw/polygon.py`): scanline fill with 3 draw modes (solid, blend, page-copy)
- **Video** (`aw/video.py`): 4 framebuffer pages (320x200, 4bpp packed), palette management
- **Resource loader** (`aw/resource.py`): supports DOS and GOG 20th Anniversary Edition data formats
- **HAL abstraction** (`aw/hal.py`): display, input, timer, file interfaces for hardware portability

## Requirements

- **Python 3.x** or **MicroPython unix port**
- **Game data files** from the GOG [Another World - 20th Anniversary Edition](https://www.gog.com/en/game/another_world_20th_anniversary_edition) (the `game/DAT/` directory)

## Quick Start

```bash
# Clone the repo
git clone https://github.com/mattytrentini/micropython_another_world.git
cd micropython_another_world

# Copy your GOG game data into the repo root
# (you need the game/DAT/ directory with FILE###.DAT files)

# Run with CPython (terminal display)
python3 main.py . --debug

# Run with MicroPython unix port
micropython main.py . --debug

# Start at a specific level
python3 main.py . 16002          # Water (first gameplay level)
python3 main.py . 16003          # Prison
```

## Controls

| Key | Action |
|-----|--------|
| Arrow keys / WASD | Move |
| Space / Enter | Action (run, kick, interact) |
| Q / Escape | Quit |
| P | Pause (debug mode) |
| N | Step one frame (debug mode) |

## Display Backends

**Terminal** (default): Renders using ANSI true-color escape sequences with Unicode half-block characters. Works in any modern terminal.

**SDL2** (branch `sdl2-backend`): Windowed display with hardware scaling and proper key-up/key-down detection. Requires `libsdl2-dev`.

```bash
python3 main.py . --sdl
```

## Project Structure

```
aw/                  Core engine (hardware-agnostic)
  vm.py              Bytecode interpreter
  video.py           Framebuffer management
  polygon.py         Scanline polygon renderer
  resource.py        Game data loader (DOS + 20th Anniversary)
  bytekiller.py      Resource decompression
  engine.py          Main game loop
  hal.py             HAL base classes
  font.py            8x8 font data
  strings.py         Game string table
  consts.py          Constants and tables
  mixer.py           Audio stub

hal_unix/            Unix port HAL implementations
  display_terminal.py  ANSI terminal display
  input_unix.py        Keyboard input
  timer_unix.py        Timer
  file_unix.py         Filesystem access

tools/               Development utilities
  disasm.py            Bytecode disassembler
  dump_memlist.py      Game data inspector

tests/               Test suite (64+ tests)
```

## Tools

```bash
# Inspect game data files
python3 tools/dump_memlist.py .

# Disassemble bytecode for a level
python3 -c "
from aw.resource import Resource
from hal_unix.file_unix import UnixFile
from tools.disasm import Disassembler
res = Resource(UnixFile('.')); res.detect_format(); res.read_memlist()
res.setup_part(16001)
for addr, text in Disassembler(res.seg_code).disasm_all():
    print('{:04X}: {}'.format(addr, text))
"

# Capture a frame as PNG
python3 tests/capture_frame.py . 50 frame.ppm
```

## References

This project was built from analysis of two GPL-licensed C++ reference implementations:

- [cyxx/rawgl](https://github.com/cyxx/rawgl) — Gregory Montoir's multi-platform reimplementation
- [fabiensanglard/Another-World-Bytecode-Interpreter](https://github.com/fabiensanglard/Another-World-Bytecode-Interpreter) — Fabien Sanglard's clean bytecode interpreter
- [Fabien Sanglard's technical articles](https://fabiensanglard.net/another_world_polygons/index.html) on the polygon engine

## Status

- Intro cinematic plays correctly
- Multiple levels tested (Water, Prison, Cite)
- Level transitions work (registers preserved across parts)
- Terminal display with debug mode (frame counter, pause/step)
- SDL2 backend on separate branch (needs WSLg or native X11)
- Audio not yet implemented (stubbed out)

## License

The engine code is original work. Game data files are not included and must be obtained separately.
