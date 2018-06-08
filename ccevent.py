# -*- coding: utf-8 -*-

import re
from collections import defaultdict

class Colors:
    # Terminal escape codes
    DGRAY = '\033[90m'
    FAIL = '\033[91m'
    LGREEN = '\033[92m'
    LYELLOW = '\033[93m'
    LBLUE = '\033[94m'
    NO_COLOR = '\033[0m'

# Known binaries
# TODO: use a tree-like structure here?
COLOR_MAP = {
    # utilities -> GRAY
    '/bin/cat': Colors.DGRAY,
    '/bin/uname': Colors.DGRAY,
    '/bin/sh': Colors.DGRAY,
    '/bin/ln': Colors.DGRAY,
    '/bin/ls': Colors.DGRAY,
    '/bin/mv': Colors.DGRAY,
    '/bin/rm': Colors.DGRAY,
    '/bin/mkdir': Colors.DGRAY,
    '/bin/rmdir': Colors.DGRAY,
    '/usr/bin/less': Colors.DGRAY,
    '/usr/bin/sudo': Colors.DGRAY,
    '/bin/bash': Colors.DGRAY,
    '/bin/tar': Colors.DGRAY,
    '/bin/date': Colors.DGRAY,
    '/bin/gzip': Colors.DGRAY,
    '/bin/sed': Colors.DGRAY,
    '/bin/grep': Colors.DGRAY,
    '/usr/bin/diff': Colors.DGRAY,
    '/usr/bin/dpkg': Colors.DGRAY,
    '/usr/bin/dpkg-query': Colors.DGRAY,
    '/usr/bin/awk': Colors.DGRAY,
    '/usr/bin/arch': Colors.DGRAY,
    '/usr/bin/expr': Colors.DGRAY,
    '/usr/bin/gawk': Colors.DGRAY,
    '/usr/bin/basename': Colors.DGRAY,
    '/usr/bin/env': Colors.DGRAY,
    '/usr/bin/find': Colors.DGRAY,
    '/usr/bin/nice': Colors.DGRAY,
    '/usr/bin/sort': Colors.DGRAY,
    '/usr/bin/print': Colors.DGRAY,
    '/usr/bin/wget': Colors.DGRAY,
    '/usr/bin/which': Colors.DGRAY,
    '/usr/bin/touch': Colors.DGRAY,
    # host translators -> LYELLOW
    '/usr/bin/yasm': Colors.LYELLOW,
    '/usr/bin/ar': Colors.LYELLOW,
    '/usr/bin/as': Colors.LYELLOW,
    '/usr/bin/x86_64-linux-gnu-as': Colors.LYELLOW,
    '/usr/bin/ranlib': Colors.LYELLOW,
    '/usr/bin/ld': Colors.LYELLOW,
    '/usr/bin/gcc': Colors.LYELLOW,
    # TODO: use regexes instead of per-version keys
    '/usr/lib/gcc/x86_64-linux-gnu/4.8/cc1': Colors.LYELLOW,
    '/usr/lib/gcc/x86_64-linux-gnu/4.8/cc1plus': Colors.LYELLOW,
    '/usr/lib/gcc/x86_64-linux-gnu/4.8/collect2': Colors.LYELLOW,
    '/usr/lib/gcc/x86_64-linux-gnu/7/cc1': Colors.LYELLOW,
    '/usr/lib/gcc/x86_64-linux-gnu/7/cc1plus': Colors.LYELLOW,
    '/usr/lib/gcc/x86_64-linux-gnu/7/collect2': Colors.LYELLOW,
    '/usr/lib/llvm-3.6/bin/clang': Colors.LYELLOW,
    '/usr/lib/llvm-3.6/bin/clang++': Colors.LYELLOW,
    '/usr/bin/cc': Colors.LYELLOW,
    '/usr/bin/g++': Colors.LYELLOW,
    '/usr/bin/clang': Colors.LYELLOW,
    '/usr/bin/clang++': Colors.LYELLOW,
    # build tools
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
    '/usr/bin/python2.7': Colors.LBLUE,
    '/usr/bin/python3': Colors.LBLUE,
    '/usr/bin/perl': Colors.LBLUE,
    '/usr/bin/tclsh8.6': Colors.LBLUE,
}


def get_color(exepath: str) -> str:
    color = COLOR_MAP.get(exepath, Colors.NO_COLOR)
    return color


def _parse_pid(s: str) -> int:
    """
    123(ab) -> 123
    """
    try:
        return int(s[:s.index('(')])
    except ValueError:  # '(' not found
        return int(s)

# def _parse_evt_args(e: dict) -> dict:
#     def split_kv(s: str) -> str:
#         try:
#             i = s.index('=')
#             return s[:i], s[i+1:]
#         except ValueError:
#             print("no = in :" + s)

#     # def parse_env(env: str) -> dict:
#     #     # base64 str -> bytes -> str
#     #     env = base64.b64decode(env).decode("utf-8")
#     #     env = [split_kv(a) for a in env.split('\x00') if a]
#     #     return {k: v for k, v in env}

#     # TODO: handle something like:
#     # 'res=61211(code) exe=/usr/share/code/code --unity-launch args= '
#     #           'tid=11013(code) pid=11013(code) ptid=1751(init) cwd= '
#     #           'fdlimit=4096 pgft_maj=146 pgft_min=61427 vm_size=1421332 '
#     #           'vm_rss=106824 vm_swap=0 comm=code '

#     args = e.pop('evt.args').rstrip().split(' ')
#     igno = ['cgroups', 'fdlimit', 'vm_size',
#             'vm_rss', 'vm_swap', 'pgft_maj', 'pgft_min']
#     args = {k: v for k, v in [split_kv(a) for a in args] if k not in igno}

#     # parse out env variables
#     # args['env'] = parse_env(args['env'])
#     if 'env' in args:
#         args.pop('env')
#     e.update(args)

#     return e        


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

    @property
    def color(self):
        return get_color(self.exepath)

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
        