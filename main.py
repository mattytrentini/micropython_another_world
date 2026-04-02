"""Another World - MicroPython game engine entry point.

Usage:
    python3 main.py <data_dir> [part_id] [--debug]
    micropython main.py <data_dir> [part_id] [--debug]

Arguments:
    data_dir:  path to directory containing game data files
    part_id:   optional starting part (default: 16001 = intro)
               16000=protection, 16001=intro, 16002=water, etc.
    --debug:  enable debug mode (frame counter, pause/step)
    --reg=R:V set VM register R to value V before start (hex with 0x prefix)
              multiple: --reg=0x67:37,0x00:21

Controls:
    Arrow keys or WASD: movement
    Space/Enter: action
    Q or Ctrl-C: quit
    P: pause/unpause (debug mode)
    N: step one frame while paused (debug mode)
"""

import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]

    if len(args) < 1:
        print("Usage: {} <data_dir> [part_id] [--debug]".format(sys.argv[0]))
        print("\ndata_dir: path to game data files")
        print("part_id:  starting part (default 16001)")
        print("          16000=protection, 16001=intro, 16002=water")
        print("--debug: frame counter, P to pause, N to step")
        sys.exit(1)

    data_dir = args[0]
    part_id = int(args[1]) if len(args) > 1 else 16001
    debug = "--debug" in flags

    # Parse --reg=0xNN:val to pre-set VM registers for cold-starting levels
    preset_regs = {}
    for f in flags:
        if f.startswith("--reg="):
            for pair in f[6:].split(","):
                reg_s, val_s = pair.split(":")
                preset_regs[int(reg_s, 0)] = int(val_s, 0)


    # Import after arg check so errors are clearer
    from aw.engine import Engine
    from hal_unix.display_terminal import TerminalDisplay
    from hal_unix.input_unix import UnixInput
    from hal_unix.timer_unix import UnixTimer
    from hal_unix.file_unix import UnixFile

    display = TerminalDisplay(scale=2, show_frame=debug)
    inp = UnixInput()
    timer = UnixTimer()
    file_hal = UnixFile(data_dir)

    engine = Engine(display, inp, timer, file_hal)
    engine.debug = debug

    try:
        engine.init(start_part=part_id)
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
