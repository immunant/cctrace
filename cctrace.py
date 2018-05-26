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
PP = pprint.PrettyPrinter(indent=2)
LANG_IS_UTF8 = os.environ.get('LANG', '').lower().endswith('utf-8')
STY = ContStyle if LANG_IS_UTF8 else AsciiStyle


NODES = dict()

def parse_exit_evt(e: dict) -> dict:
    def split_kv(s: str) -> str:
        try:
            i = s.index('=')
            return s[:i], s[i+1:]
        except ValueError:
            print("no = in :" + s)

    def parse_env(env: str) -> dict:
        # base64 str -> bytes -> str
        env = base64.b64decode(env).decode("utf-8")
        env = [split_kv(a) for a in env.split('\x00') if a]
        return {k: v for k, v in env}

    args = e['evt.args'].rstrip().split(' ')
    args = e.pop('evt.args').rstrip().split()
    igno = ['cgroups', 'fdlimit', 'vm_size', 'vm_rss', 'vm_swap', 'pgft_maj', 'pgft_min']
    args = {k: v for k, v in [split_kv(a) for a in args] if k not in igno}

    # parse out env variables
    # args['env'] = parse_env(args['env'])
    args.pop('env')
    e.update(args)
    return e


class CCNode(Node):
    pass
    # separator = "|"


def handle_events(enterevt: dict, exitevt: dict):
    exitevt = parse_exit_evt(exitevt)

    # ignore non-successful events
    if exitevt.pop('res') != '0':
        return

    # PP.pprint(enterevt)
    # print("-------------")
    # PP.pprint(exitevt)
    # quit(1)

    parent, parent_pid = enterevt['proc.exepath'], int(enterevt['proc.ppid'])
    child, child_pid = exitevt['proc.exepath'], exitevt['pid']
    child_pid = int(child_pid[:child_pid.index('(')])  # 123(ab) -> 123
    assert parent_pid != child_pid

    pcolor = COLOR_MAP.get(parent, NO_COLOR)
    rnode = CCNode(parent, count=1, color=pcolor, pid=parent_pid)
    pnode = NODES.setdefault(parent_pid, rnode)

    # deduplicate child nodes
    for cnode in pnode.children:
        if cnode.name == child:
            # found existing child!
            cnode.count += 1
            break
    else:  # didn't find existing child!
        ccolor = COLOR_MAP.get(child, NO_COLOR)
        NODES[child_pid] = CCNode(child,
                                  parent=pnode,
                                  count=1,
                                  color=ccolor,
                                  pid=child_pid)

    # while pnode.parent:
    #     pnode = pnode.parent
    # assert pnode.is_root

    # TODO: handle multiple roots
    roots = [n for n in NODES.values() if n.is_root]

    # DISPLAY PART
    # TODO: extract function

    sys.stdout.write(u"\u001b[" + str(1000) + "D")  # Move left
    sys.stdout.write(u"\u001b[" + str(1000) + "A")  # Move up
    for i, root in enumerate(roots):
        for pre, _, node in RenderTree(pnode, style=STY):
            line = "{}{}{} ({})".format(pre, node.color, node.name, node.pid)
            line = line + NO_COLOR
            # TODO: does not count escape codes or not?
            line = line.ljust(COLUMNS)
            print(line)
    if len(roots) > 2:
        quit(1)


def main():

    enter_events = dict()  # key'ed by thread id

    try:
        while True:
            line = sys.stdin.readline()
            evt = json.loads(line)  # type: dict

            tid = int(evt['thread.tid'])
            if evt['evt.dir'] == '>':  # enter events
                enter_events[tid] = evt
            else:  # exit events
                assert evt['evt.dir'] == '<'
                enter_event = enter_events.pop(tid)
                handle_events(enter_event, evt)
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
