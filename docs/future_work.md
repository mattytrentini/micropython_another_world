# Future Work

Tracked issues, planned features, and known limitations.

## Filed Issues

- [#1 Password/checkpoint system](https://github.com/mattytrentini/micropython_another_world/issues/1) — implement password entry or save states for starting later levels

## Input & Display

- **SDL2 backend** — branch `sdl2-backend` exists but needs WSLg/X11 to test. Provides proper key-up/key-down detection and hardware-scaled window. Should be merged once verified.
- **Terminal input limitations** — simultaneous keys unreliable, running is difficult. Fundamental limitation of terminal input; SDL2 or hardware buttons is the real fix.

## Audio

- **Sound effects and music** — currently stubbed out (`aw/mixer.py`). The game has a 4-channel PCM mixer and MOD-style music sequencer (SfxPlayer). Would significantly improve the experience. Reference: `vm-architecture.md` section 11.

## Hardware Targets

- **RP2040/RP2350 HAL** — the stated goal of the project. Needs display driver (SPI LCD), GPIO button input, and memory optimization (128KB framebuffers are tight on 264KB RP2040, comfortable on 520KB RP2350).
- **ESP32-S3 HAL** — more RAM available (512KB SRAM + optional PSRAM), better fit for the 128KB framebuffer requirement.
- **Performance optimization for MicroPython** — polygon scanline fill is the hot path. Escalation: `@micropython.native` → `@micropython.viper` → C user module.

## Engine Completeness

- **DOS data format support** — `resource.py` has the code but it's untested (we only have GOG 20th Anniversary data). ByteKiller decompression needs verification with real DOS bank files.
- **Bitmap loading (Amiga bitplane→chunky)** — RT_BITMAP resources aren't handled. Some levels may use full-screen bitmaps for backgrounds.
- **All levels tested end-to-end** — only intro, water, prison, and cite have been tested. Arene (16005), Luxe (16006), Final (16007) need verification.

## Quality of Life

- **`framebuf.FrameBuffer` integration** — planned in the original design but not yet used for page operations. Would give C-speed `fill()`, `blit()`, `scroll()`, and `fb.poly()` for solid-color polygon fills on MicroPython.
