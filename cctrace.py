#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import pprint
import shutil

from collections import defaultdict
from anytree import Node, RenderTree
from anytree.render import AsciiStyle, ContStyle
# from anytree.iterators.levelordergroupiter import LevelOrderGroupIter

from ccevent import CCEvent

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
    '/usr/bin/sudo': DGRAY,
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
    '/usr/bin/x86_64-linux-gnu-as': LYELLOW,
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
    '/usr/bin/cc': LYELLOW,
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
SHELL = os.environ.get('SHELL', '').lower()

UNKNOWN_PROC_LABEL = "[unknown executable]"
UNKNOWN_PROC_COLOR = FAIL

SYSDIG_NA = '<NA>'

nodes_by_pid = dict()  # holds nodes for active processes
roots = set()  # holds root nodes, never shrinks


class CCNode(Node):
    separator = "|"

    def hash_subtree(self):
        res = 31 * hash(self.name)
        for child in self.children:
            res = res * 31 + child.hash_subtree()
        return res

    def __hash__(self):
        return hash(self.name)


def print_tree():
    sys.stdout.write(u"\u001b[" + str(1000) + "D")  # move left
    sys.stdout.write(u"\u001b[" + str(1000) + "A")  # move up
    duplicates = set()
    forrest = []
    for root in roots:
        for pre, _, node in RenderTree(root, style=STY):
            # TODO: more robust pruning of nodes
            marker = node.hash_subtree()
            if node.parent:
                marker = marker * 31 + hash(node.parent.name)
            if marker in duplicates:
                continue
            else:
                duplicates.add(marker)
            # skip leaf nodes representing utility processes
            if node.is_leaf and node.color == DGRAY:
                continue
            # skip child nodes of configure calls
            if node.parent and node.parent.name.endswith("configure"):
                continue
            # line = "{}{}{}".format(pre, node.color, node.name)
            line = "{}{}{} ({})".format(pre, node.color, node.name, node.pid)
            line = line + NO_COLOR
            # TODO: do manual justification to ignore escape codes
            forrest.append(line.ljust(COLUMNS))

    if len(forrest) > LINES:
        forrest = forrest[:LINES - 1]

    print("\n".join(forrest))


def handle_execve(exitevt: CCEvent):
    # exitevt = parse_evt_args(exitevt)

    child_pid, parent_pid = exitevt.pid, exitevt.ppid

    child = exitevt.exepath
    # sometimes 'exepath' is blank. TODO: can this be avoided?
    if child == SYSDIG_NA:
        # TODO: do something less hackish
        eargs = exitevt.eargs
        if "exe=sh " in eargs:
            child = '/bin/sh'
        elif "filename=" in eargs:
            child = eargs[9:]
        else:
            print(exitevt.eargs)
            assert False

    ccolor = COLOR_MAP.get(child, NO_COLOR)

    # the lookup of the parent process can fail if the process was
    # started before we started running sysdig
    rnode = CCNode(UNKNOWN_PROC_LABEL,
                   color=UNKNOWN_PROC_COLOR, pid=parent_pid)
    pnode = nodes_by_pid.setdefault(parent_pid, rnode)

    cnode = nodes_by_pid.get(child_pid, None)
    if cnode:
        cnode.name = child
        cnode.color = ccolor
    else:
        # happens if a process executes multiple execve calls
        nodes_by_pid[child_pid] = \
            CCNode(child, parent=pnode, color=ccolor, pid=child_pid)

    print_tree()


def handle_clone(exitevt: CCEvent):
    child_pid, parent_pid = exitevt.pid, exitevt.ppid
    assert child_pid > 0, "Unexpected child pid: {}".format(child_pid)
    assert parent_pid != child_pid

    color = COLOR_MAP.get(exitevt.exepath, NO_COLOR)
    pnode = nodes_by_pid.setdefault(parent_pid,
                                    CCNode(exitevt.exepath, color=color, pid=parent_pid))
    cnode = nodes_by_pid.setdefault(child_pid,
                                    CCNode(exitevt.exepath, parent=pnode, color=color,
                                           pid=child_pid))

    # update ROOTS (ignoring anyhing but shells)
    if pnode.is_root and pnode.name == SHELL:
        roots.add(pnode)


def handle_procexit(evt: CCEvent):
    pid = evt.pid
    nodes_by_pid.pop(pid, None)  # removes node if present


def main():
    try:
        # TODO: use asyncio to handle input events?
        while True:
            line = sys.stdin.readline().rstrip()
            while not line.endswith('##'):
                line += sys.stdin.readline().rstrip()

            evt = CCEvent.parse(line)

            if evt.type == 'execve':
                handle_execve(evt)
            elif evt.type == 'clone':
                # clone returns twice; once for parent and child.
                if not "res=0 " in evt.eargs:
                    continue  # ignore parent event
                handle_clone(evt)
            elif evt.type == 'procexit':
                handle_procexit(evt)
            else:
                assert False, "Unexpected event type: " + str(evt.type)

    except KeyboardInterrupt:
        sys.stdout.write("\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
