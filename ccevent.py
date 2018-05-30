# -*- coding: utf-8 -*-

import re


def _parse_pid(s: str) -> int:
    """
    123(ab) -> 123
    """
    try:
        return int(s[:s.index('(')])
    except ValueError:  # '(' not found
        return int(s)


class CCEvent(object):

    def __init__(self, tid: int, _type: str, exepath: str, pname: str,
                 pid: int, ppid: int, pargs: str, eargs: str):
        self.tid = tid
        self.type = _type
        self.exepath = exepath
        self.pname = pname
        self.pid = pid
        self.ppid = ppid
        self.pargs = pargs
        self.eargs = eargs

    @staticmethod
    def parse(line: str) -> object:
        tokens = line.split('#')

        return CCEvent(tid=_parse_pid(tokens[0]),
                       _type=tokens[1],
                       exepath=tokens[2],
                       pname=tokens[3],
                       pid=_parse_pid(tokens[4]),
                       ppid=_parse_pid(tokens[5]),
                       pargs=tokens[6],
                       eargs=tokens[7]
                       )
