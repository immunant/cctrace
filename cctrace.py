#!/usr/bin/env python3

import os
import sys
import shutil
from collections import defaultdict

# Terminal color codes
NO_COLOR = '\033[0m'
DGRAY = '\033[90m'
FAIL = '\033[91m'
LGREEN = '\033[92m'
LYELLOW = '\033[93m'
LBLUE = '\033[94m'

# Terminal dimensions
COLUMNS, LINES = shutil.get_terminal_size((80, 20))

# Known binaries
# TODO: use a tree-like structure here?
COLOR_MAP = {
    # utilities -> GRAY
    '/bin/uname': DGRAY,
    '/bin/sh': DGRAY,
    '/bin/rm': DGRAY,
    '/usr/bin/less': DGRAY,
    '/bin/bash': DGRAY,
    '/bin/tar': DGRAY,
    '/bin/gzip': DGRAY,
    '/bin/gzip': DGRAY,
    '/bin/sed': DGRAY,
    '/usr/bin/diff': DGRAY,
    '/usr/bin/dpkg': DGRAY,
    '/usr/bin/dpkg-query': DGRAY,
    '/usr/bin/awk': DGRAY,
    '/usr/bin/gawk': DGRAY,
    '/usr/bin/env': DGRAY,
    '/usr/bin/find': DGRAY,
    '/usr/bin/ar': DGRAY,
    '/usr/bin/nice': DGRAY,
    '/usr/bin/sort': DGRAY,
    '/usr/bin/print': DGRAY,
    '/usr/bin/wget': DGRAY,
    '/usr/bin/which': DGRAY,
    # host translators -> YELLOW
    '/usr/bin/yasm': LYELLOW,
    '/usr/bin/as': LYELLOW,
    '/usr/bin/ranlib': LYELLOW,
    '/usr/bin/ld': LYELLOW,
    '/usr/bin/gcc': LYELLOW,
    '/usr/lib/gcc/x86_64-linux-gnu/7/cc1': LYELLOW,
    '/usr/lib/gcc/x86_64-linux-gnu/7/collect2': LYELLOW,
    '/usr/bin/g++': LYELLOW,
    '/usr/bin/clang': LYELLOW,
    '/usr/bin/clang++': LYELLOW,
    # build tools
    '/usr/bin/make': LBLUE,
    '/usr/bin/cmake': LBLUE,
    '/usr/bin/ninja': LBLUE,
    '/usr/bin/pkg-config': LBLUE,
    # scripting engines -> BLUE
    '/usr/bin/python2.7': LBLUE,
    '/usr/bin/python3': LBLUE,
    '/usr/bin/perl': LBLUE,
    '/usr/bin/tclsh8.6': LBLUE,
}
COLOR_MAP = defaultdict(str, COLOR_MAP)
LASTLINES = 0  # how many lines did last call to update_display print?


def update_display(binaries):
    global LASTLINES
    sys.stdout.write(u"\u001b[" + str(COLUMNS) + "D")  # Move left
    if LASTLINES > 1:
        sys.stdout.write(u"\u001b[" + str(LASTLINES - 1) + "A")  # Move up

    def format(instr):
        if instr in COLOR_MAP:
            instr = COLOR_MAP[instr] + instr + NO_COLOR
        return instr.ljust(COLUMNS)

    # save screen space by not showing utilities
    lines = [format(b) for b in sorted(binaries) if COLOR_MAP[b] != DGRAY]
    # lines = [format(b) for b in sorted(binaries)]

    if len(lines) > LINES:
        msg = "... {} additional binaries not shown".format(len(lines)-LINES+1)
        msg = msg.ljust(COLUMNS)
        lines = lines[:LINES-1] + [msg]
    LASTLINES = len(lines)
    sys.stdout.write("\n".join(lines))


BINARIES = set()
BIN_COUNT = 0


def process_evt(evt: str):
    global BINARIES, BIN_COUNT
    atoms = evt.split()
    assert atoms[0].startswith("filename="), "unexpected: " + line
    binary = atoms[0][9:]
    # we don't monitor whether execve fails or not, so skip
    # calls that try to execute non-exsistent files.
    if not os.path.exists(binary):
        return

    BINARIES.add(binary)
    if len(BINARIES) > BIN_COUNT:
        BIN_COUNT += 1
        update_display(BINARIES)


def main():
    def readline():
        return sys.stdin.readline().rstrip()

    try:
        while True:
            line = readline()
            while line.endswith('\\'):
                line += readline()
            process_evt(line)
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
