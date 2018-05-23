#!/usr/bin/env python3

import sys
import shutil

# Terminal escape codes
OKBLUE = '\033[94m'
OKGREEN = '\033[92m'
WARNING = '\033[93m'
FAIL = '\033[91m'
NO_COLOUR = '\033[0m'

# Terminal dimensions
COLUMNS, LINES = shutil.get_terminal_size((80, 20))

LASTLINES = 0  # how many lines did last call to update_display print?


def update_display(binaries):
    global LASTLINES
    sys.stdout.write(u"\u001b[" + str(COLUMNS) + "D")  # Move left
    if LASTLINES > 1:
        sys.stdout.write(u"\u001b[" + str(LASTLINES - 1) + "A")  # Move up

    maxlen = max([len(b) for b in binaries])

    def pad(instr):
        return instr.ljust(COLUMNS)

    lines = [pad(b) for b in sorted(binaries)]
    LASTLINES = len(lines)
    sys.stdout.write("\n".join(lines))


if __name__ == "__main__":
    BINARIES = set()
    BIN_COUNT = 0

    try:
        for line in sys.stdin:
            atoms = line.split()
            binary = atoms[0]
            BINARIES.add(binary)
            if len(BINARIES) > BIN_COUNT:
                BIN_COUNT += 1
                update_display(BINARIES)
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        sys.stdout.flush()
        pass
