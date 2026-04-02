"""Another World — ODROID Go entry point.

Copy game data to the SD card at /game/DAT/FILE###.DAT then run this.

Controls:
    D-pad: movement
    A/B: action (run, kick, interact)
    Start: quit
    Menu: pause (debug mode)
    Select: step one frame (debug mode)
"""

import gc


def main():
    gc.collect()

    # Mount SD card first (before display init, they share SPI)
    from hal_odroid_go.sdcard import mount_sd
    if not mount_sd():
        print("ERROR: Cannot mount SD card")
        print("Ensure SD card is inserted with game data at /game/DAT/")
        return

    gc.collect()

    from aw.engine import Engine
    from hal_odroid_go.display import OdroidGoDisplay
    from hal_odroid_go.input import OdroidGoInput
    from hal_odroid_go.timer import OdroidGoTimer
    from hal_odroid_go.file import OdroidGoFile

    display = OdroidGoDisplay()
    inp = OdroidGoInput()
    timer = OdroidGoTimer()
    file_hal = OdroidGoFile("/sd")

    engine = Engine(display, inp, timer, file_hal)

    try:
        engine.init(start_part=16001)
        engine.run()
    finally:
        inp.shutdown()
        display.shutdown()


main()
