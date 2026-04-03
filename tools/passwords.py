"""List all Another World checkpoint passwords.

Usage: python3 tools/passwords.py
"""

import sys
sys.path.insert(0, ".")

from aw.consts import PASSWORDS

LEVEL_NAMES = {
    16001: "Intro",
    16002: "Water",
    16003: "Prison",
    16004: "Cite",
    16005: "Arene",
    16006: "Luxe",
    16007: "Final",
}


def main():
    print("{:<10s} {:>5s}  {:>5s}  {}".format(
        "Password", "Chk", "Part", "Level"))
    print("-" * 40)

    entries = sorted(PASSWORDS.items(), key=lambda x: (x[1][1], x[1][0]))
    for pw, (checkpoint, part_id) in entries:
        level = LEVEL_NAMES.get(part_id, "?")
        print("{:<10s} {:>5d}  {:>5d}  {}".format(pw, checkpoint, part_id, level))

    print("\n{} passwords".format(len(PASSWORDS)))
    print("\nUsage: python3 main.py <data_dir> <password> [--sdl]")


if __name__ == "__main__":
    main()
