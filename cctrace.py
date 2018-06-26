#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import argparse

from anytree import Node, RenderTree
from anytree.render import AsciiStyle, ContStyle

from ccevent import CCEvent, Colors, get_color


LANG_IS_UTF8 = os.environ.get('LANG', '').lower().endswith('utf-8')
STY = ContStyle if LANG_IS_UTF8 else AsciiStyle
SHELL = os.environ.get('SHELL', '').lower()

UNKNOWN_PROC_LABEL = "[unknown executable]"
UNKNOWN_PROC_COLOR = Colors.FAIL

SYSDIG_NA = '<NA>'


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


nodes_by_pid = dict()  # holds nodes for active processes
roots = set()  # holds root nodes, never shrinks


def print_tree(roots: set) -> None:
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
            forrest.append(line)

    print("\n".join(forrest))


_eargs_re = re.compile(r".*exe=(.*)\sargs=")


def handle_execve(exitevt: CCEvent) -> CCEvent:
    child_pid, parent_pid = exitevt.pid, exitevt.ppid

    child = exitevt.exepath
    # sometimes 'exepath' is blank. TODO: can this be avoided?
    if child == SYSDIG_NA:
        eargs = exitevt.eargs
        m = _eargs_re.match(eargs)
        if m:
            child = m.group(1)
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
        cnode = CCNode(child, parent=pnode, pid=child_pid)
        nodes_by_pid[child_pid] = cnode
    
    return cnode


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


def _check_multicompiler_prefix(prefix: str) -> bool:
    slugs = [
        'bin/clang',
        'bin/clang++',
        'bin/llvm-nm',
        'bin/llvm-ar',
        'bin/llvm-ranlib',
        'bin/ld.gold',
    ] 

    if not os.path.isdir(prefix):
        return False

    for s in slugs:
        if not os.path.exists(os.path.join(prefix, s)):
            return False

    # TODO: invoke clang --version and look for multicompiler in output
    return True


def _parse_args():
    """
    define and parse command line arguments here.
    """
    desc = 'listen for compiler invocations.'
    parser = argparse.ArgumentParser(description=desc)
    mp_default = os.getenv('HOME')
    mp_default = os.path.join(mp_default,
                              "selfrando-testing/local")
    parser.add_argument('-m', '--multicompiler-prefix', 
                        default=mp_default,
                        action='store', dest='multicompiler_prefix',
                        help='set multicompiler install prefix')

    args = parser.parse_args()
    if not _check_multicompiler_prefix(args.multicompiler_prefix):
        args.multicompiler_prefix = None
    return args


def main():
    args = _parse_args()

    try:
        while True:
            line = sys.stdin.readline().rstrip()
            while not line.endswith('##'):
                line += sys.stdin.readline().rstrip()

            evt = CCEvent.parse(line)

            if evt.type == 'execve':
                cnode = handle_execve(evt)
                # TODO: take action based on args
                # TODO: want mode that prints if compiler AND not under
                # multicompiler prefix. Print tree from root node.
                if args.multicompiler_prefix and \
                   cnode.name.startswith(args.multicompiler_prefix):
                   print("mc: {} ({})".format(cnode.name, cnode.pid))

            elif evt.type == 'clone':
                # clone returns twice; once for parent and child.
                if "res=0 " not in evt.eargs:
                    continue  # ignore parent event
                handle_clone(evt)
            elif evt.type == 'procexit':
                handle_procexit(evt)
            else:
                assert False, "Unexpected event type: " + str(evt.type)

    except KeyboardInterrupt:
        print()
        print_tree(roots)


if __name__ == "__main__":
    main()
