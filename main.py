"""Another World - MicroPython game engine entry point.

Usage:
    python3 main.py <data_dir> [password|part_id] [--sdl] [--debug]
    micropython main.py <data_dir> [password|part_id] [--debug]

Arguments:
    data_dir:   path to directory containing game data files
    password:   4-letter checkpoint code (e.g. LDKD, HTDC, CLLD)
                run 'python3 tools/passwords.py' to see all codes
    part_id:    numeric starting part (default: 16001 = intro)
    --sdl:      use SDL2 window (proper input, hardware scaling)
    --debug:    enable debug mode (frame counter, pause/step)
    --reg=R:V   set VM register R to value V (hex with 0x prefix)

Controls:
    Arrow keys or WASD: movement
    Space/Enter: action
    Q or Escape: quit
    P: pause/unpause (debug mode)
    N: step one frame while paused (debug mode)
"""

import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]

    if len(args) < 1:
        print("Usage: {} <data_dir> [password|part_id] [--sdl] [--debug]".format(
            sys.argv[0]))
        print("\ndata_dir: path to game data files")
        print("password: 4-letter checkpoint code (e.g. LDKD, HTDC, CLLD)")
        print("part_id:  numeric starting part (default 16001)")
        print("--sdl:   SDL2 window (recommended)")
        print("--debug: frame counter, P to pause, N to step")
        print("\nRun 'python3 tools/passwords.py' to see all checkpoint codes")
        sys.exit(1)

    data_dir = args[0]
    part_id = 16001
    checkpoint = None

    if len(args) > 1:
        arg = args[1]
        if arg.isalpha():
            # Password lookup
            from aw.consts import PASSWORDS
            pw = arg.upper()
            if pw not in PASSWORDS:
                print("Unknown password: {}".format(arg))
                print("Run 'python3 tools/passwords.py' to see valid codes")
                sys.exit(1)
            checkpoint, part_id = PASSWORDS[pw]
        else:
            part_id = int(arg)

    use_sdl = "--sdl" in flags
    debug = "--debug" in flags

    # Parse --reg=0xNN:val to pre-set VM registers
    preset_regs = {}
    for f in flags:
        if f.startswith("--reg="):
            for pair in f[6:].split(","):
                reg_s, val_s = pair.split(":")
                preset_regs[int(reg_s, 0)] = int(val_s, 0)

    from aw.engine import Engine
    from hal_unix.file_unix import UnixFile

    if use_sdl:
        from hal_unix.sdl2_display import SDL2Display
        from hal_unix.sdl2_input import SDL2Input
        from hal_unix.sdl2_timer import SDL2Timer

        display = SDL2Display(scale=3)
        inp = SDL2Input(display)
        timer = SDL2Timer()
    else:
        from hal_unix.display_terminal import TerminalDisplay
        from hal_unix.input_unix import UnixInput
        from hal_unix.timer_unix import UnixTimer

        display = TerminalDisplay(scale=2, show_frame=debug)
        inp = UnixInput()
        timer = UnixTimer()

    file_hal = UnixFile(data_dir)
    engine = Engine(display, inp, timer, file_hal)
    engine.debug = debug

    try:
        engine.init(start_part=part_id)
        if checkpoint is not None:
            engine.vm.regs[0] = checkpoint
        for reg, val in preset_regs.items():
            engine.vm.regs[reg] = val
        engine.run()
    except KeyboardInterrupt:
        pass
    finally:
        inp.shutdown()
        display.shutdown()


if __name__ == "__main__":
    main()
