# -*- coding: utf-8 -*-

import os
import re
import subprocess as sp
from typing import Optional, List


class Colors:
    # Terminal escape codes
    DGRAY = '\033[90m'
    LRED = '\033[91m'
    LGREEN = '\033[92m'
    LYELLOW = '\033[93m'
    LBLUE = '\033[94m'
    LMAGENTA = '\033[95m'
    LCYAN = '\033[96m'
    NO_COLOR = '\033[0m'


# Known binaries
COLOR_MAP = {
    # utilities -> GRAY (all matched by regex now)
    # host translators -> LYELLOW
    '/usr/bin/yasm': Colors.LYELLOW,
    '/usr/bin/ar': Colors.LYELLOW,
    '/usr/bin/as': Colors.LYELLOW,
    '/usr/bin/x86_64-linux-gnu-as': Colors.LYELLOW,
    '/usr/bin/ranlib': Colors.LYELLOW,
    '/usr/bin/ld': Colors.LYELLOW,
    '/usr/bin/gcc': Colors.LYELLOW,
    '/usr/bin/cc': Colors.LYELLOW,
    '/usr/bin/g++': Colors.LYELLOW,
    '/usr/bin/clang': Colors.LYELLOW,
    '/usr/bin/clang++': Colors.LYELLOW,
    # build tools -> BLUE
    '/usr/bin/make': Colors.LBLUE,
    '/usr/bin/cmake': Colors.LBLUE,
    '/usr/bin/ccmake': Colors.LBLUE,
    '/usr/bin/ctest': Colors.LBLUE,
    '/usr/bin/cpack': Colors.LBLUE,
    '/usr/bin/qmake': Colors.LBLUE,
    '/usr/bin/scons': Colors.LBLUE,
    '/usr/bin/ninja': Colors.LBLUE,
    '/usr/bin/pkg-config': Colors.LBLUE,
    '/usr/bin/bear': Colors.LBLUE,
    # scripting engines -> BLUE
    '/usr/bin/perl': Colors.LBLUE,
    '/usr/bin/ruby': Colors.LBLUE,
}

_known_tools = dict()
compiler_drivers = dict()
_host_python_re = re.compile(r"/usr/(local/)?bin/python(\d\.\d|\d)?")
_host_tclsh_re = re.compile(r"/usr/(local/)?bin/tclsh(\d\.\d|\d)?")
_host_util_re = re.compile(r"/(usr/)?bin/.*")
_build_tool_re = re.compile(r"[^\0]+/((c|cc|g|q)?make|cpack|ctest|scons|ninja|bear|ccache)")
_gcc_lib_re = re.compile(r"/usr/lib/gcc/[^\0]+/(\d\.\d|\d)/(cc(1|1plus)|collect2)")
_llvm_lib_re = re.compile(r"/usr/lib/llvm-[\d\.]+/bin/clang(\+\+)?")
# binaries that are likely compiler drivers
_compiler_driver_re = re.compile(r"[^\0]+/(clang(\+\+)?|gcc|g\+\+|suncc|icc|cc|c\+\+)")


def get_compiler_ver(exepath: str) -> Optional[str]:
    """
    TODO: move compiler identification logic into separate file?
    """
    exepath = os.path.realpath(exepath)  # canonicalize path
    try:
        p = sp.Popen([exepath, '--version'], stdout=sp.PIPE, stderr=sp.PIPE)
        stdout, stderr = p.communicate()
        ver = stdout.split(b'\n', 1)[0]  # get first line
        # print("{} -> {}".format(exepath, ver))
        ver = ver.decode()  # bytes -> str
        return re.sub(r"\s\(.*\)", "", ver)  # remove parenthetical info
    except OSError:
        return None


def get_color(exepath: str) -> str:
    color = _known_tools.get(exepath, None)
    if color:
        return color

    if _host_python_re.match(exepath) or \
            _host_tclsh_re.match(exepath) or \
            _build_tool_re.match(exepath):
        color = Colors.LBLUE
    elif _gcc_lib_re.match(exepath) or \
            _llvm_lib_re.match(exepath):
        color = Colors.LYELLOW
    elif _compiler_driver_re.match(exepath):
        color = Colors.LRED
        if exepath not in compiler_drivers:
            compiler_drivers[exepath] = get_compiler_ver(exepath)
    else:
        color = COLOR_MAP.get(exepath, Colors.NO_COLOR)

    if color == Colors.NO_COLOR and _host_util_re.match(exepath):
        color = Colors.DGRAY

    _known_tools[exepath] = color
    return color


def _parse_pid(s: bytes) -> int:
    """
    123(ab) -> 123
    """
    try:
        return int(s[:s.index(b'(')])
    except ValueError:  # '(' not found
        try:
            return int(s)
        except ValueError:
            print(s)
            assert False


class CCEvent(object):
    separator = b'#'

    def __init__(self, tid: int, _type: bytes, exepath: str, pname: str,
                 pid: int, ppid: int, pargs: bytes, eargs: bytes):
        self.tid = tid
        self.type = _type
        self.exepath = exepath
        self.pname = pname
        self.pid = pid
        self.ppid = ppid
        self.pargs = pargs
        self.eargs = eargs

    @property
    def color(self):
        return get_color(self.exepath)

    @staticmethod
    def parse(line: bytes) -> object:
        tokens = line.split(CCEvent.separator)  # type: List[Optional[bytes]]
        if len(tokens) == 7:
            tokens.append(None)
        return CCEvent(tid=_parse_pid(tokens[0]),
                       _type=tokens[1],
                       exepath=str(tokens[2], encoding='utf-8'),
                       pname=str(tokens[3], encoding='utf-8'),
                       pid=_parse_pid(tokens[4]),
                       ppid=_parse_pid(tokens[5]),
                       pargs=tokens[6],
                       eargs=tokens[7])

    def __str__(self):
        return "#".join([str(self.tid), str(self.type), self.exepath,
                         self.pname, str(self.pid),
                         str(self.ppid),
                         str(self.pargs), str(self.eargs)])
