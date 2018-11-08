import os
import re
import sys
import logging
import unittest
from collections import defaultdict

from itertools import chain

from tools import ToolType
from ccevent import Colors


class PolicyError(object):
    def __init__(self, message, tt, expected, observed):
        self.tt = tt
        self.message = message
        self.expected = expected
        self.observed = observed

    @staticmethod
    def argument_mismatch(tt, expected, observed):
        message = "missing argument to {}"
        message = message.format(tt.name)
        return PolicyError(message, tt, expected, observed)

    @staticmethod
    def tool_mismatch(tt, expected, observed):
        message = "not using expected {}"
        message = message.format(tt.name)
        return PolicyError(message, tt, expected, observed)

    def print(self, observed_diag=None) -> None:
        emsg = "{}Error{}: {}.\n"
        emsg += "Expected: {}{}{}\nObserved: "
        cfmt = [Colors.LRED, Colors.NO_COLOR, self.message,
                Colors.LYELLOW, self.expected, Colors.NO_COLOR]
        emsg = emsg.format(*cfmt)
        if observed_diag:
            emsg += "\n" + observed_diag
        else:
            emsg += self.observed

        print(emsg)

    def log(self, observed_diag=None) -> None:
        emsg = "{}.\nExpected: {}\nObserved:"
        emsg = emsg.format(self.message, self.expected)
        if observed_diag:
            emsg += "\n" + observed_diag
        else:
            emsg += self.observed

        logging.error(emsg)


class Policy(object):
    # tool types that we can configure and police
    tools = [ToolType.c_compiler,
             ToolType.cxx_compiler,
             ToolType.linker,
             ToolType.archiver,
             ToolType.indexer,
             ToolType.sym_lister,
             ToolType.assembler]
    # the expected schema for .json configuration files
    schema = {
        "name": str,
        "keep_going": bool,
    }
    # update schema to require that all tool entries are dictionaries
    schema = dict(chain(schema.items(), {t.name: dict for t in tools}.items()))

    # regexes to determine why compiler was invoked
    compile_re = re.compile(r"(\s|^)-c(\s|$)")
    conftest_re = re.compile(r".*conftest\.c\s*$")
    preprocess_re = re.compile(r"(\s|^)-E(\s|$)")
    version_check_re = re.compile(r"(\s|^)(-?-(vers|versi|versio|q?version)|-v|-V)(\s|$)")

    def __init__(self):
        self.name = "default"
        self.keep_going = False
        self.ignore_prefix = None
        self._path_expect = defaultdict(set)        # type: dict[ToolType, str]
        self._args_expect = dict()                  # type: dict[ToolType, list[str]]
        self._compile_args_expect = dict()          # type: dict[ToolType, list[str]]
        self._compile_link_args_expect = dict()     # type: dict[ToolType, list[str]]

    def expect_tool_path(self, t: ToolType, path: str) -> None:
        """
        note: don't try to validate paths, they may
        come from another environment, e.g., docker.
        """
        path = os.path.expanduser(path)
        path = os.path.realpath(path)
        self._path_expect[t].add(path)

    def expect_tool_args(self, t: ToolType, args: list,
                         expect_when_compiling=False,
                         expect_when_linking=False) -> None:
        if expect_when_compiling and expect_when_linking:
            assert False, "invalid args passed to expect_tool_args"
        elif expect_when_compiling:
            assert(t.is_compiler())
            self._compile_args_expect[t] = args
        elif expect_when_linking:
            assert(t.is_compiler())
            self._compile_link_args_expect[t] = args
        else:
            self._args_expect[t] = args

    def configure(self, config: dict) -> None:

        # type check top-level elements of policy file
        for (k, v) in config.items():
            exp_typ = Policy.schema.get(k, None)
            if not exp_typ:
                emsg = "Error, unknown configuration key: " + str(k)
                sys.exit(emsg)
            elif exp_typ != type(v):
                emsg = "Error, expected key {} to have type {}; actual type {}"
                emsg = emsg.format(k, exp_typ, type(v))
                sys.exit(emsg)

        # path and argument configuation
        for t in Policy.tools:
            tool_cfg = config.pop(t.name, None)  # type: dict
            if tool_cfg:
                path_emsg = "Error, path must be a string or list of strings, was "
                # paths
                path = tool_cfg.pop("path", None)  # type: str
                if path:
                    if type(path) != str and type(path) != list:
                        path_emsg += path.__class__.__name__
                        sys.exit(path_emsg)
                    elif type(path) == str:
                        self.expect_tool_path(t, path)
                    elif type(path) == list:
                        for p in path:
                            if type(p) != str:
                                path_emsg += path.__class__.__name__
                                sys.exit(path_emsg)
                            self.expect_tool_path(t, p)

                targs = tool_cfg.pop("args", None)  # type: list[str]
                if targs:
                    if type(targs) != list:
                        emsg = "Error, args key must be a list of strings, was "
                        emsg += targs.__class__.__name__
                        sys.exit(emsg)
                    self.expect_tool_args(t, targs)

                # compiler specific keys
                if t.is_compiler():
                    targs = tool_cfg.pop("compile_args", None)  # type: list[str]
                    if targs:
                        if type(targs) != list:
                            emsg = "Error, compile_args key must be a list of strings, was "
                            emsg += targs.__class__.__name__
                            sys.exit(emsg)
                        self.expect_tool_args(t, targs, expect_when_compiling=True)

                    targs = tool_cfg.pop("link_args", None)  # type: list[str]
                    if targs:
                        if type(targs) != list:
                            emsg = "Error, link_args key must be a list of strings, was "
                            emsg += targs.__class__.__name__
                            sys.exit(emsg)
                        self.expect_tool_args(t, targs, expect_when_linking=True)

                # did we process all configuration keys for t?
                if len(tool_cfg):
                    logging.warning("didn't understand policy for %s", t.name)

        self.name = config.pop("name", self.name)
        self.keep_going = config.pop("keep_going", self.keep_going)

    def check(self, exepath: str, args: str = "") -> PolicyError:
        tt = ToolType.from_path(exepath)  # type: ToolType

        def check_args(exp_args) -> PolicyError:
            for expected in exp_args:
                if expected not in args:
                    return PolicyError.argument_mismatch(tt,
                                                         expected,
                                                         args)
            return None

        expected_args = self._args_expect.get(tt, [])
        if tt.is_compiler():
            # look for compiler invocations that we don't care about
            if self.preprocess_re.search(args) or \
                    self.version_check_re.search(args) or \
                    self.conftest_re.search(args):
                # don't police preprocessor invocations, version checks
                # or invocations by configure scripts.
                expected_args = []
            # look for the -c flag which must either be preceeded (followed)
            # by a space or the start (end) of the line.
            elif self.compile_re.search(args):
                expected_args = list(expected_args)
                expected_args += self._compile_args_expect.get(tt, [])
            else:  # compile and link
                expected_args = list(expected_args)
                expected_args += self._compile_link_args_expect.get(tt, [])

        result = check_args(expected_args)
        if result:
            return result

        expected_paths = self._path_expect[tt]  # type: defaultdict(set)
        observed_path = os.path.realpath(exepath)
        if expected_paths:
            for expected_path in expected_paths:
                if expected_path == observed_path:
                    break
            else:  # no break -> no match
                return PolicyError.tool_mismatch(tt, expected_path, observed_path)

        return None

    def is_checked(self, exepath: str) -> bool:
        tt = ToolType.from_path(exepath)  # type: ToolType
        has_path_expect = len(self._path_expect[tt])
        has_args_expect = tt in self._args_expect
        return has_path_expect or has_args_expect


class TestPolicy(unittest.TestCase):

    invalid_path = "/no/such/path/i/really/hope/srsly/wth"
    gcc_path = "/usr/bin/gcc"
    gxx_path = "/usr/bin/g++"
    cc_args = "-O2 -g -c test.c"
    clang_path = "/usr/bin/clang"
    clangxx_path = "/usr/bin/clang++"

    def test_is_checked(self):
        p = Policy()
        self.assertFalse(p.is_checked(self.gcc_path))
        # start checking c compiler
        p.expect_tool_path(ToolType.c_compiler, self.gcc_path)
        self.assertTrue(p.is_checked(self.gcc_path))
        # C++ compiler is still not checked
        self.assertFalse(p.is_checked(self.gxx_path))
        # now, C++ compiler args are checked
        p.expect_tool_args(ToolType.cxx_compiler, ["-g"])
        self.assertTrue(p.is_checked(self.gxx_path))

    def test_check_no_config(self):
        p = Policy()
        # no config, no args -> `check` returns `None`
        c = p.check(self.gcc_path)
        self.assertIsNone(c)
        # no config -> `check` returns `None`
        c = p.check(TestPolicy.gcc_path)
        self.assertIsNone(c, self.cc_args)

    def test_check_cc_path(self):
        p = Policy()
        p.expect_tool_path(ToolType.c_compiler, self.gcc_path)
        # expected path -> `check` returns `None`
        c = p.check(self.gcc_path)
        self.assertIsNone(c)

        # invalid path -> check returns `None`
        c = p.check(self.invalid_path)
        self.assertIsNone(c)

        # clang -> check returns `PolicyError`
        c = p.check(self.clang_path)
        self.assertIsInstance(c, PolicyError)
        self.assertEqual(c.message, "not using expected c_compiler")

    def test_check_cxx_path(self):
        p = Policy()
        p.expect_tool_path(ToolType.cxx_compiler, self.gxx_path)
        # expected path -> `check` returns `None`
        c = p.check(self.gxx_path)
        self.assertIsNone(c)

        # invalid path -> check returns `None`
        c = p.check(self.invalid_path)
        self.assertIsNone(c)

        # clang -> check returns `PolicyError`
        c = p.check(self.clangxx_path)
        self.assertIsInstance(c, PolicyError)
        self.assertEqual(c.message, "not using expected cxx_compiler")

    def test_check_linker_path(self):
        p = Policy()
        p.expect_tool_path(ToolType.linker, "/usr/bin/ld")
        # expected path -> `check` returns `None`
        c = p.check("/usr/bin/ld")
        self.assertIsNone(c)

        # invalid path -> check returns `None`
        c = p.check(self.invalid_path)
        self.assertIsNone(c)

        # clang -> check returns `PolicyError`
        c = p.check("/my/custom/path/ld")
        self.assertIsInstance(c, PolicyError)
        self.assertEqual(c.message, "not using expected linker")

    def test_check_cc_args(self):
        tt = ToolType.c_compiler
        p = Policy()
        # args we expect no matter whether we're compiling or linking
        p._args_expect[tt] = ["-flto"]

        # passing expected parameters -> `None`
        c = p.check(self.gcc_path, "-flto")
        self.assertIsNone(c)

        # not passing expected parameters -> `PolicyError`
        c = p.check(self.gcc_path, "--version")
        self.assertIsInstance(c, PolicyError)
        self.assertEqual(c.message, "missing argument to c_compiler")

        # args we expect when we're only compiling
        p.expect_tool_args(tt, ["-g", "-O2", "-Wall"], expect_when_compiling=True)

        # passing expected parameters when compiling -> `None`
        c = p.check(self.gcc_path, "-c -flto -g -O2 -Wall")
        self.assertIsNone(c)

        # not passing expected parameters when compiling -> `PolicyError`
        c = p.check(self.gcc_path, "-c -g -O2 -Wall")
        self.assertIsInstance(c, PolicyError)
        self.assertEqual(c.message, "missing argument to c_compiler")

        c = p.check(self.gcc_path, "-c -flto -Wall")
        self.assertIsInstance(c, PolicyError)
        self.assertEqual(c.message, "missing argument to c_compiler")

        # args we expect when we're linking
        p.expect_tool_args(tt, ["-lm", "-ldl"], expect_when_linking=True)

        # passing expected parameters when linking -> `None`
        c = p.check(self.gcc_path, "-flto -lm -ldl")
        self.assertIsNone(c, "problem handling linker args")

        # missing linker parameters when linking -> `PolicyError`
        c = p.check(self.gcc_path, "-flto -lm")
        self.assertIsInstance(c, PolicyError)
        self.assertEqual(c.message, "missing argument to c_compiler")


if __name__ == '__main__':
    unittest.main()
