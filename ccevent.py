# -*- coding: utf-8 -*-

import base64

# from typing import Optional, List  # not available in Python3.4

from tools import ToolType


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



def get_color(exepath: str) -> str:
    color = get_color.cache.get(exepath, None)
    if color:
        return color

    tt = ToolType.from_path(exepath)
    if tt.is_compiler_or_linker():
        color = Colors.LRED
    elif tt.is_compiler_helper() or \
            tt == ToolType.archiver or \
            tt == ToolType.indexer:
        color = Colors.LYELLOW
    elif tt == ToolType.interpreter or tt == ToolType.builder:
        color = Colors.LBLUE
    elif tt == ToolType.util:
        color = Colors.DGRAY
    else:
        color = Colors.NO_COLOR

    get_color.cache[exepath] = color
    return color


get_color.cache = dict()


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

    def _parse_eargs_field(self, fieldname: bytes) -> str:
        atoms = self.eargs.split()
        flen = len(fieldname)
        try:
            for a in atoms:
                if a.startswith(fieldname):
                    # get list of bytearrays
                    payload = base64.decodebytes(a[flen:]).split(b'\0') 
                    payload = map(lambda n: n.decode(), payload)
                    return payload
        except:
            pass
        return None
        # return "(could not decode {})".format(fieldname.decode())

    @property
    def color(self):
        return get_color(self.exepath)

    @property
    def args(self) -> str:
        args = self._parse_eargs_field(b"args=")
        if args:
            return " ".join(args)
        else:
            return ""

    @property
    def env(self) -> dict:
        pairs = self._parse_eargs_field(b"env=")
        res = dict()
        for p in pairs:
            i = p.find("=")
            res[p[:i]] = p[i+1:]
        return res

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
