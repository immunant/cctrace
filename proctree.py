import os
import re

from anytree import Node, RenderTree
from anytree.render import AsciiStyle, ContStyle

from ccevent import CCEvent, get_color, Colors
from tools import get_tool_ver


LANG_IS_UTF8 = os.environ.get('LANG', '').lower().endswith('utf-8')
STY = ContStyle if LANG_IS_UTF8 else AsciiStyle
# SHELL = os.environ.get('SHELL', '').lower()


class CCNode(Node):
    separator = b"|"

    @property
    def color(self):
        return get_color(self.name)

    def hash_subtree(self):
        res = [hash(self.name)]
        for child in self.children:
            res.append(child.hash_subtree)
        return hash(tuple(res))

    def hash_roots(self):
        res = [hash(self.name)]
        if not self.is_root:
            res.append(self.parent.hash_roots())
        return hash(tuple(res))

    def __hash__(self):
        return hash(self.name)


SYSDIG_NA = '<NA>'
UNKNOWN_PROC_LABEL = "[unknown executable]"
UNKNOWN_PROC_COLOR = Colors.LRED


class ProcTree(object):
    _eargs_re = re.compile(r".*exe=(.*)\sargs=")

    def __init__(self):
        self.nodes_by_pid = dict()  # holds nodes for active processes
        self.roots = set()  # holds root nodes; never shrinks

    def handle_procexit(self, evt: CCEvent):
        self.nodes_by_pid.pop(evt.pid, None)  # remove node if present

    def handle_clone(self, evt: CCEvent):
        child_pid, parent_pid = evt.pid, evt.ppid
        assert child_pid > 0, "Unexpected child pid: {}".format(child_pid)
        assert parent_pid != child_pid

        pnode = self.nodes_by_pid.setdefault(parent_pid,
                                             CCNode(evt.exepath, pid=parent_pid))
        cnode = self.nodes_by_pid.setdefault(child_pid, None)
        if not cnode:
            cnode = CCNode(evt.exepath, parent=pnode, pid=child_pid)
            self.nodes_by_pid[child_pid] = cnode

        if pnode.is_root:
            self.roots.add(pnode)

    def handle_execve(self, evt: CCEvent):
        child_pid, parent_pid = evt.pid, evt.ppid

        child = evt.exepath
        # sometimes 'exepath' is blank. TODO: can this be avoided?
        if child == SYSDIG_NA:
            eargs = str(evt.eargs)
            m = ProcTree._eargs_re.match(eargs)
            if m:
                child = m.group(1)
            elif "filename=" in eargs:
                child = eargs[9:]
            else:
                print(evt.eargs)
                assert False

        # the lookup of the parent process can fail if the process was
        # started before we started running sysdig
        rnode = CCNode(UNKNOWN_PROC_LABEL, pid=parent_pid)
        pnode = self.nodes_by_pid.setdefault(parent_pid, rnode)

        cnode = self.nodes_by_pid.get(child_pid, None)
        if cnode:
            cnode.name = child
        else:
            # happens if a process executes multiple execve calls
            cnode = CCNode(child, parent=pnode, pid=child_pid)
            self.nodes_by_pid[child_pid] = cnode

    def print_single_branch(self, evt: CCEvent):
        print(self.format_single_branch(evt))

    def format_single_branch(self, evt: CCEvent, fancy_output=True) -> str:
        """
        printes tree from evt node to its (observed) root proc.
        """
        dgray = Colors.DGRAY if fancy_output else ""
        nocol = Colors.NO_COLOR if fancy_output else ""

        branch = set()
        root = self.nodes_by_pid[evt.pid]
        # prints the node of interest as an only child
        if root.parent:
            root.parent.children = [root]
        branch.add(root)
        while not root.is_root:
            root = root.parent
            branch.add(root)

        lines = []  # List[str]
        indent = 0
        sty = STY if fancy_output else AsciiStyle
        for pre, _, node in RenderTree(root, style=sty):
            if node not in branch:
                continue
            ncolor = get_color(node.name) if sty == ContStyle else ""
            line = "{}{}{} ({})".format(pre, ncolor, node.name, node.pid)
            # nodes representing compiler drivers or linkers have version info
            cc_ver = get_tool_ver(node.name)
            if cc_ver:
                line += dgray + " " + cc_ver
            line = line + nocol
            lines.append(line)
            indent = len(pre)

        # print args of event
        line = " " * indent + dgray
        line += evt.args + nocol
        lines.append(line)

        env = evt.env
        pwd = env.get("PWD", None)
        if pwd:
            line = " " * indent + "$PWD=" + pwd
            lines.append(line)

        return "\n".join(lines)

    def print_tree(self) -> None:
        """
        NOTE: this function is called right before cctrace.py exits and only once.
        NOTE: this is a best effort to compactly represent the process tree.
        """

        def keeper(n: CCNode) -> bool:
            """
            Returns True if this node is interesting, False otherwise.
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

        roots = [r for r in self.roots if keeper(r)]

        duplicates = set()
        forrest = []

        # first remove duplicate subtrees
        for root in roots:
            for pre, _, node in RenderTree(root, style=STY):

                marker = node.hash_subtree()
                if node.parent:
                    marker = hash((marker, node.parent.hash_roots()))
                if marker in duplicates:
                    par = node.parent
                    if par:
                        par.children = [c for c in par.children if c != node]
                else:
                    duplicates.add(marker)

        # ... then print the forrest
        for root in roots:
            for pre, _, node in RenderTree(root, style=STY):

                ncolor = node.color

                # color policy-checked nodes green
                if p.is_checked(node.name) and p.check(node.name) is None:
                    ncolor = Colors.LGREEN

                # line = "{}{}{}".format(pre, ncolor, node.name)
                line = "{}{}{} ({})".format(pre, ncolor, node.name, node.pid)
                # nodes representing compiler drivers have version information
                cc_ver = get_tool_ver(node.name)
                if cc_ver:
                    line += Colors.DGRAY + " " + cc_ver
                line = line + Colors.NO_COLOR
                forrest.append(line)

        print("\n".join(forrest))
