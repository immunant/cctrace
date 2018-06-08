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

from ccevent import CCEvent, Colors, get_color

# Terminal dimensions
COLUMNS, LINES = shutil.get_terminal_size((80, 20))


PP = pprint.PrettyPrinter(indent=2)
LANG_IS_UTF8 = os.environ.get('LANG', '').lower().endswith('utf-8')
STY = ContStyle if LANG_IS_UTF8 else AsciiStyle
SHELL = os.environ.get('SHELL', '').lower()

UNKNOWN_PROC_LABEL = "[unknown executable]"
UNKNOWN_PROC_COLOR = Colors.FAIL

SYSDIG_NA = '<NA>'

nodes_by_pid = dict()  # holds nodes for active processes
roots = set()  # holds root nodes, never shrinks


class CCNode(Node):
    separator = "|"

    @property
    def color(self):
        return get_color(self.name)


    def hash_subtree(self):
        res = hash(self.name)
        for child in self.children:
            res = res * 31 + child.hash_subtree()
        return res

    def hash_roots(self):
        res = hash(self.name)
        if not self.is_root:
            res = res * 31 + self.parent.hash_roots()
        return res

    def __hash__(self):
        return hash(self.name)


print_tree_last_lines = 0  # how many lines did print_tree output last time?


def print_tree():
    global print_tree_last_lines
    sys.stdout.write(u"\u001b[" + str(1000) + "D")  # move left
    sys.stdout.write(u"\u001b[" + str(1000) + "A")  # move up
    duplicates = set()
    forrest = []
    for root in roots:
        for pre, _, node in RenderTree(root, style=STY):

            marker = node.hash_subtree()
            if node.parent:
                marker = marker * 31 + node.parent.hash_roots()
            if marker in duplicates:
                continue
            else:
                duplicates.add(marker)
            # skip leaf nodes representing utility processes
            if node.is_leaf and node.color == Colors.DGRAY:
                continue
            # skip child nodes of configure calls
            if node.parent and node.parent.name.endswith("configure"):
                continue
            # line = "{}{}{}".format(pre, node.color, node.name)
            line = "{}{}{} ({})".format(pre, node.color, node.name, node.pid)
            line = line + Colors.NO_COLOR
            # TODO: do manual justification to ignore escape codes
            forrest.append(line.ljust(COLUMNS))

    if len(forrest) > LINES:
        # forrest = forrest[:LINES - 1]
        forrest = forrest[-LINES:]

    blank_lines_needed = max(0, print_tree_last_lines - len(forrest))
    print_tree_last_lines = len(forrest)

    forrest += [" " * COLUMNS for _ in range(blank_lines_needed)]

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

    # the lookup of the parent process can fail if the process was
    # started before we started running sysdig
    rnode = CCNode(UNKNOWN_PROC_LABEL, pid=parent_pid)
    pnode = nodes_by_pid.setdefault(parent_pid, rnode)

    cnode = nodes_by_pid.get(child_pid, None)
    if cnode:
        cnode.name = child
    else:
        # happens if a process executes multiple execve calls
        nodes_by_pid[child_pid] = \
            CCNode(child, parent=pnode, pid=child_pid)

    print_tree()


def handle_clone(exitevt: CCEvent):
    child_pid, parent_pid = exitevt.pid, exitevt.ppid
    assert child_pid > 0, "Unexpected child pid: {}".format(child_pid)
    assert parent_pid != child_pid

    pnode = nodes_by_pid.setdefault(parent_pid,
                                    CCNode(exitevt.exepath, pid=parent_pid))
    cnode = nodes_by_pid.setdefault(child_pid, None)
    if not cnode:
        nodes_by_pid[child_pid] = CCNode(exitevt.exepath, parent=pnode, pid=child_pid)

    # sanity check that all children have distinct pid's
    # child_pids = set()
    # for child in pnode.children:
    #     assert child.pid not in child_pids
    #     child_pids.add(child.pid)

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
