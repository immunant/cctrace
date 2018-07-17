#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import logging
import argparse

from anytree import Node, RenderTree
from anytree.render import AsciiStyle, ContStyle

from ccevent import CCEvent, Colors, get_color, get_compiler_ver


LANG_IS_UTF8 = os.environ.get('LANG', '').lower().endswith('utf-8')
STY = ContStyle if LANG_IS_UTF8 else AsciiStyle
SHELL = os.environ.get('SHELL', '').lower()

UNKNOWN_PROC_LABEL = "[unknown executable]"
UNKNOWN_PROC_COLOR = Colors.LRED

SYSDIG_NA = '<NA>'


class CCNode(Node):
    separator = b"|"

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


def print_tree(roots: set, args) -> None:
    """
    NOTE: this function is called right before cctrace.py exits and only once.
    """

    def keeper(n) -> bool:
        """
        Return True if this node is a keeper, otherwise False.
        """
        # configure processes are never keepers
        if n.name.endswith("configure"):
            return False

        # prune children
        n.children = filter(lambda c: keeper(c), n.children)

        # boring leafs are never keepers
        if n.is_leaf and n.color in [Colors.DGRAY, Colors.NO_COLOR]:
            return False

        return True

    roots = [r for r in roots if keeper(r)]

    duplicates = set()
    forrest = []
    special_prefix = args.multicompiler_prefix  # type: Optional[str]
    special_prefix = "\0invalid" if not special_prefix else special_prefix

    for root in roots:
        for pre, _, node in RenderTree(root, style=STY):

            marker = node.hash_subtree()
            ncolor = node.color
            if node.parent:
                marker = marker * 31 + node.parent.hash_roots()
            if marker in duplicates:
                continue
            else:
                duplicates.add(marker)

            # color multicompiler nodes green
            if node.name.startswith(special_prefix):
                ncolor = Colors.LGREEN

            # line = "{}{}{}".format(pre, ncolor, node.name)
            line = "{}{}{} ({})".format(pre, ncolor, node.name, node.pid)
            # nodes representing compiler drivers have version information
            cc_ver = get_compiler_ver(node.name)
            if cc_ver:
                line += Colors.DGRAY + " " + cc_ver
            line = line + Colors.NO_COLOR
            forrest.append(line)

    print("\n".join(forrest))


def print_single_branch(evt: CCEvent):
    """
    printes tree from evt node to its (observed) root proc.
    """
    branch = set()
    root = nodes_by_pid[evt.pid]
    # prints the node of interest as an only child
    if root.parent:
        root.parent.children = [root]
    branch.add(root)
    while not root.is_root:
        root = root.parent
        branch.add(root)

    lines = []  # List[str]
    indent = 0
    for pre, _, node in RenderTree(root, style=STY):
        if node not in branch:
            continue
        line = "{}{}{} ({})".format(pre, node.color, node.name, node.pid)
        # nodes representing compiler drivers have version information
        cc_ver = get_compiler_ver(node.name)
        if cc_ver:
            line += Colors.DGRAY + " " + cc_ver
        line = line + Colors.NO_COLOR
        lines.append(line)
        indent = len(pre)

    # print args of event
    line = " " * indent + Colors.DGRAY
    line += evt.args + Colors.NO_COLOR
    lines.append(line)

    env = evt.env
    pwd = env.get("PWD", None)
    if pwd:
        line = " " * indent + "$PWD=" + pwd
        lines.append(line)

    print("\n".join(lines))


def handle_execve(exitevt: CCEvent) -> CCEvent:
    child_pid, parent_pid = exitevt.pid, exitevt.ppid

    child = exitevt.exepath
    # sometimes 'exepath' is blank. TODO: can this be avoided?
    if child == SYSDIG_NA:
        eargs = str(exitevt.eargs)
        m = handle_execve.eargs_re.match(eargs)
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


handle_execve.eargs_re = re.compile(r".*exe=(.*)\sargs=")


def handle_clone(exitevt: CCEvent):
    child_pid, parent_pid = exitevt.pid, exitevt.ppid
    assert child_pid > 0, "Unexpected child pid: {}".format(child_pid)
    assert parent_pid != child_pid

    pnode = nodes_by_pid.setdefault(parent_pid,
                                    CCNode(exitevt.exepath, pid=parent_pid))
    cnode = nodes_by_pid.setdefault(child_pid, None)
    if not cnode:
        cnode = CCNode(exitevt.exepath, parent=pnode, pid=child_pid)
        nodes_by_pid[child_pid] = cnode

    # sanity check that all children have distinct pid's
    # child_pids = set()
    # for child in pnode.children:
    #     assert child.pid not in child_pids
    #     child_pids.add(child.pid)

    # update ROOTS (ignoring anyhing but shells)
    if pnode.is_root and pnode.name == SHELL:
        roots.add(pnode)


def handle_procexit(evt: CCEvent, args):
    pid = evt.pid
    nodes_by_pid.pop(pid, None)  # removes node if present


def _check_multicompiler_prefix(prefix: str) -> bool:
    slugs = [
        'bin/clang',
        'bin/clang++',
        'bin/llvm-nm',
        'bin/llvm-ar',
        'bin/llvm-ranlib',
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

    parser.add_argument('-n', '--no-multicompiler-warn',
                        default=True,
                        action='store_false', dest='multicompiler_warn',
                        help="don't warn when using non-diversifying compiler")

    args = parser.parse_args()
    if not _check_multicompiler_prefix(args.multicompiler_prefix):
        args.multicompiler_prefix = None
    return args


def _setup_logging():
    logging.basicConfig(
        filename="cctrace.log",
        format="%(asctime)-15s:%(levelname)s:%(message)s",
        filemode='w',
        level=logging.DEBUG)
    logging.debug("argv: %s", " ".join(sys.argv))


def main():
    args = _parse_args()
    _setup_logging()
    mc_prefix = args.multicompiler_prefix
    eol = b'##\n'
    try:
        while True:
            # read input as bytes since its not guaranteed to be UTF-8
            line = sys.stdin.buffer.readline()
            while not line.endswith(eol):
                line += sys.stdin.buffer.readline()

            evt = CCEvent.parse(line)

            if evt.type == b'execve':
                cnode = handle_execve(evt)

                # TODO: this is ad hoc; include direction in format?
                if evt.eargs.startswith(b'filename='):
                    continue  # this is the enter event
                
                # NOTE: assumes that compilers are always execve'd
                cc_ver = get_compiler_ver(evt.exepath)
                if cc_ver:
                    logging.info("%d:%s %s", evt.pid, evt.exepath, evt.args)

                if args.multicompiler_warn and mc_prefix:
                    if cc_ver and not evt.exepath.startswith(mc_prefix):
                        print("Warning: not using multicompiler here:")
                        print_single_branch(evt)
                        quit(1)

            elif evt.type == b'clone':
                # clone returns twice; once for parent and child.
                if b"res=0 " not in evt.eargs:
                    continue  # ignore parent event
                handle_clone(evt)
            elif evt.type == b'procexit':
                handle_procexit(evt, args)
            else:
                assert False, "Unexpected event type: " + str(evt.type)

    except KeyboardInterrupt:
        print()
        print_tree(roots, args)


if __name__ == "__main__":
    main()
