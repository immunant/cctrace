#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import base64
import pprint
import shutil

from collections import defaultdict
from anytree import Node, RenderTree
from anytree.node.exceptions import TreeError
from anytree.render import AsciiStyle, ContStyle
from anytree.iterators.levelordergroupiter import LevelOrderGroupIter

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
    '/bin/cat': DGRAY,
    '/bin/uname': DGRAY,
    '/bin/sh': DGRAY,
    '/bin/ln': DGRAY,
    '/bin/ls': DGRAY,
    '/bin/mv': DGRAY,
    '/bin/rm': DGRAY,
    '/bin/mkdir': DGRAY,
    '/bin/rmdir': DGRAY,
    '/usr/bin/less': DGRAY,
    '/bin/bash': DGRAY,
    '/bin/tar': DGRAY,
    '/bin/date': DGRAY,
    '/bin/gzip': DGRAY,
    '/bin/sed': DGRAY,
    '/bin/grep': DGRAY,
    '/usr/bin/diff': DGRAY,
    '/usr/bin/dpkg': DGRAY,
    '/usr/bin/dpkg-query': DGRAY,
    '/usr/bin/awk': DGRAY,
    '/usr/bin/arch': DGRAY,
    '/usr/bin/expr': DGRAY,
    '/usr/bin/gawk': DGRAY,
    '/usr/bin/basename': DGRAY,
    '/usr/bin/env': DGRAY,
    '/usr/bin/find': DGRAY,
    '/usr/bin/nice': DGRAY,
    '/usr/bin/sort': DGRAY,
    '/usr/bin/print': DGRAY,
    '/usr/bin/wget': DGRAY,
    '/usr/bin/which': DGRAY,
    '/usr/bin/touch': DGRAY,
    # host translators -> YELLOW
    '/usr/bin/yasm': LYELLOW,
    '/usr/bin/ar': LYELLOW,
    '/usr/bin/as': LYELLOW,
    '/usr/bin/ranlib': LYELLOW,
    '/usr/bin/ld': LYELLOW,
    '/usr/bin/gcc': LYELLOW,
    # TODO: use regexes instead of per-version keys
    '/usr/lib/gcc/x86_64-linux-gnu/4.8/cc1': LYELLOW,
    '/usr/lib/gcc/x86_64-linux-gnu/4.8/cc1plus': LYELLOW,
    '/usr/lib/gcc/x86_64-linux-gnu/4.8/collect2': LYELLOW,
    '/usr/lib/gcc/x86_64-linux-gnu/7/cc1': LYELLOW,
    '/usr/lib/gcc/x86_64-linux-gnu/7/cc1plus': LYELLOW,
    '/usr/lib/gcc/x86_64-linux-gnu/7/collect2': LYELLOW,
    '/usr/lib/llvm-3.6/bin/clang': LYELLOW,
    '/usr/lib/llvm-3.6/bin/clang++': LYELLOW,
    '/usr/bin/g++': LYELLOW,
    '/usr/bin/clang': LYELLOW,
    '/usr/bin/clang++': LYELLOW,
    # build tools
    '/usr/bin/make': LBLUE,
    '/usr/bin/cmake': LBLUE,
    '/usr/bin/ccmake': LBLUE,
    '/usr/bin/ctest': LBLUE,
    '/usr/bin/cpack': LBLUE,
    '/usr/bin/qmake': LBLUE,
    '/usr/bin/scons': LBLUE,
    '/usr/bin/ninja': LBLUE,
    '/usr/bin/pkg-config': LBLUE,
    '/usr/bin/bear': LBLUE,
    # scripting engines -> BLUE
    '/usr/bin/python2.7': LBLUE,
    '/usr/bin/python3': LBLUE,
    '/usr/bin/perl': LBLUE,
    '/usr/bin/tclsh8.6': LBLUE,
}
COLOR_MAP = defaultdict(str, COLOR_MAP)
PP = pprint.PrettyPrinter(indent=2)
LANG_IS_UTF8 = os.environ.get('LANG', '').lower().endswith('utf-8')
STY = ContStyle if LANG_IS_UTF8 else AsciiStyle

UNKNOWN_PROC_LABEL = "[unknown executable]"
UNKNOWN_PROC_COLOR = FAIL

NODES = dict()

def parse_evt_args(e: dict) -> dict:
    def split_kv(s: str) -> str:
        try:
            i = s.index('=')
            return s[:i], s[i+1:]
        except ValueError:
            print("no = in :" + s)

    # def parse_env(env: str) -> dict:
    #     # base64 str -> bytes -> str
    #     env = base64.b64decode(env).decode("utf-8")
    #     env = [split_kv(a) for a in env.split('\x00') if a]
    #     return {k: v for k, v in env}

    # TODO: handle something like:
    # 'res=61211(code) exe=/usr/share/code/code --unity-launch args= '
    #           'tid=11013(code) pid=11013(code) ptid=1751(init) cwd= '
    #           'fdlimit=4096 pgft_maj=146 pgft_min=61427 vm_size=1421332 '
    #           'vm_rss=106824 vm_swap=0 comm=code '

    args = e.pop('evt.args').rstrip().split(' ')
    igno = ['cgroups', 'fdlimit', 'vm_size', 'vm_rss', 'vm_swap', 'pgft_maj', 'pgft_min']
    args = {k: v for k, v in [split_kv(a) for a in args] if k not in igno}

    # parse out env variables
    # args['env'] = parse_env(args['env'])
    if 'env' in args: args.pop('env')
    e.update(args)

    return e


class CCNode(Node):
    separator = "|"


def _parse_pid(s: str):
    """
    123(ab) -> 123
    """
    try:
        return int(s[:s.index('(')]) 
    except ValueError:  # '(' not found
        return int(s)

def handle_execve(exitevt: dict):
    """
    TODO: deal with PID wrap-around.
    """
    # exitevt = parse_evt_args(exitevt)

    parent_pid, child_pid = int(exitevt['proc.ppid']), int(exitevt['proc.pid']) 
    child = exitevt['proc.exepath']
    ccolor =  COLOR_MAP.get(child, NO_COLOR)

    # sometimes 'proc.exepath' is blank. might be during high load.
    if not child.strip():
       child = UNKNOWN_PROC_LABEL
       ccolor = UNKNOWN_PROC_COLOR

    # the lookup of the parent process can fail if the process was 
    # started before we started running sysdig
    rnode = CCNode(UNKNOWN_PROC_LABEL, color=UNKNOWN_PROC_COLOR, pid=parent_pid)
    pnode = NODES.setdefault(parent_pid, rnode)

    cnode = NODES.get(child_pid, None)
    if cnode:
        cnode.name = child
        cnode.color = ccolor
    else:
        # happens if a process executes multiple execve calls
        NODES[child_pid] = \
            CCNode(child, parent=pnode, color=ccolor, pid=child_pid)


    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    # display process tree                   #
    #                                        #
    # TODO: extract into separate function   #
    # TODO: better pruning of boring nodes   #
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

    # handle multiple roots
    roots = [n for n in NODES.values() if n.is_root and n.name != UNKNOWN_PROC_LABEL]
    sys.stdout.write(u"\u001b[" + str(1000) + "D")  # move left
    sys.stdout.write(u"\u001b[" + str(1000) + "A")  # move up
    for root in roots:
        for pre, _, node in RenderTree(root, style=STY):
            # skip leaf nodes representing utility processes
            if node.is_leaf and node.color == DGRAY:
                continue
            line = "{}{}{} ({})".format(pre, node.color, node.name, node.pid)
            line = line + NO_COLOR
            # TODO: do manual justification to ignore escape codes
            line = line.ljust(COLUMNS)
            print(line)
       

def handle_clone(exitevt: dict):
    exepath, parent_pid = exitevt['proc.exepath'], int(exitevt['proc.ppid'])
    child_pid = int(exitevt['proc.pid'])
    assert child_pid > 0

    assert parent_pid != child_pid

    color = COLOR_MAP.get(exepath, NO_COLOR)
    pnode = NODES.setdefault(parent_pid, 
                             CCNode(exepath, color=color, pid=parent_pid))
    cnode = NODES.setdefault(child_pid, 
                             CCNode(exepath, parent=pnode, color=color, pid=child_pid))


def main():
    try:
        while True:
            line = sys.stdin.readline()
            evt = json.loads(line)  # type: dict

            if evt['evt.type'] == 'execve':
                handle_execve(evt)
            elif evt['evt.type'] == 'clone':  
                # clone returns twice; once for parent and child.
                if not "res=0 " in evt['evt.args']:
                    continue  # ignore parent event
                handle_clone(evt)

    except KeyboardInterrupt:
        sys.stdout.write("\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
