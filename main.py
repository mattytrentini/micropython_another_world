"""Another World - MicroPython game engine entry point.

Usage:
    python3 main.py <data_dir> [part_id]
    micropython main.py <data_dir> [part_id]

Arguments:
    data_dir: path to directory containing game data files
              (memlist.bin, bank01-bank0d)
    part_id:  optional starting part (default: 16001 = intro)
              16000=copy protection, 16001=intro, 16002=water, etc.

Controls:
    Arrow keys or WASD: movement
    Space/Enter: action
    Q or Ctrl-C: quit
"""

import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: {} <data_dir> [part_id]".format(sys.argv[0]))
        print("\ndata_dir: path to game data files (memlist.bin, bank01-bank0d)")
        print("part_id:  starting part (default 16001)")
        print("          16000=protection, 16001=intro, 16002=water")
        sys.exit(1)

    data_dir = sys.argv[1]
    part_id = int(sys.argv[2]) if len(sys.argv) > 2 else 16001

    # Import after arg check so errors are clearer
    from aw.engine import Engine
    from hal_unix.display_terminal import TerminalDisplay
    from hal_unix.input_unix import UnixInput
    from hal_unix.timer_unix import UnixTimer
    from hal_unix.file_unix import UnixFile

    display = TerminalDisplay(scale=2)  # 160 columns
    inp = UnixInput()
    timer = UnixTimer()
    file_hal = UnixFile(data_dir)

    engine = Engine(display, inp, timer, file_hal)

    try:
        engine.init(start_part=part_id)
        engine.run()
    except KeyboardInterrupt:
        pass
    finally:
        inp.shutdown()
        display.shutdown()


if __name__ == "__main__":
    main()
