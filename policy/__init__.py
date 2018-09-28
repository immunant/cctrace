import os
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

    def __init__(self):
        self.name = "default"
        self.keep_going = False
        self.ignore_prefix = None
        self._path_expect = defaultdict(set)        # type: dict[ToolType, str]
        self._args_expect = dict()                  # type: dict[ToolType, list[str]]
        self._compile_args_expect = dict()          # type: dict[ToolType, list[str]]
        self._compile_link_args_expect = dict()     # type: dict[ToolType, list[str]]

    def configure_path_expect(self, t: ToolType, path: str) -> None:
        """
        note: don't try to validate paths, they may
        come from another environment, e.g., docker.
        """
        path = os.path.expanduser(path)
        path = os.path.realpath(path)
        self._path_expect[t].add(path)

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
                        self.configure_path_expect(t, path)
                    elif type(path) == list:
                        for p in path:
                            if type(p) != str:
                                path_emsg += path.__class__.__name__
                                sys.exit(path_emsg)
                            self.configure_path_expect(t, p)

                targs = tool_cfg.pop("args", None)  # type: list[str]
                if targs:
                    if type(targs) != list:
                        emsg = "Error, args key must be a list of strings, was "
                        emsg += targs.__class__.__name__
                        sys.exit(emsg)
                    self._args_expect[t] = targs

                # compiler specific keys
                if t.is_compiler():
                    targs = tool_cfg.pop("compile_args", None)  # type: list[str]
                    if targs:
                        if type(targs) != list:
                            emsg = "Error, compile_args key must be a list of strings, was "
                            emsg += targs.__class__.__name__
                            sys.exit(emsg)
                        self._compile_args_expect[t] = targs

                    targs = tool_cfg.pop("link_args", None)  # type: list[str]
                    if targs:
                        if type(targs) != list:
                            emsg = "Error, link_args key must be a list of strings, was "
                            emsg += targs.__class__.__name__
                            sys.exit(emsg)
                        self._compile_link_args_expect[t] = targs

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
            if " -c " in args:  # only compile
                expected_args += self._compile_args_expect.get(tt, [])
            else:  # compile and link
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

    def test_check_no_config(self):
        """
        tests `check` method without configuration
        """
        p = Policy()
        # no config, no args -> `check` returns `None`
        c = p.check(self.gcc_path)
        self.assertIsNone(c)
        # no config -> `check` returns `None`
        c = p.check(TestPolicy.gcc_path)
        self.assertIsNone(c, self.cc_args)

    def test_check_cc_path(self):
        p = Policy()
        p.configure_path_expect(ToolType.c_compiler, self.gcc_path)
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
        p.configure_path_expect(ToolType.cxx_compiler, self.gxx_path)
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


    def test_check_cc_args(self):
        p = Policy()
        # args we expect no matter whether we're compiling or linking
        p._args_expect[ToolType.c_compiler] = ["-flto"]

        # passing expected parameters -> `None`
        c = p.check(self.gcc_path, "-flto")
        self.assertIsNone(c)

        # not passing expected parameters -> `PolicyError`
        c = p.check(self.gcc_path, "--version")
        self.assertIsInstance(c, PolicyError)
        self.assertEqual(c.message, "missing argument to c_compiler")

        # args we expect when we're only compiling
        p._compile_args_expect = ["-g", "-O2", "-Wall"]

        # passing expected parameters when compiling -> `None`
        c = p.check(self.gcc_path, "-c -flto -g -O2 -Wall")
        self.assertIsNone(c)

        # not passing expected parameters when compiling -> `PolicyError`
        c = p.check(self.gcc_path, "-c -g -O2 -Wall")
        self.assertIsInstance(c, PolicyError)
        self.assertEqual(c.message, "missing argument to c_compiler")

        # TODO: should have compile args expect for c and c++ compilers separately
        # TODO: this test craps out
        c = p.check(self.gcc_path, "-c -flto -Wall")
        self.assertIsInstance(c, PolicyError)
        self.assertEqual(c.message, "missing argument to c_compiler")

        # # args we expect when we're linking
        # p._compile_link_args_expect = ["-lm", "-ldl"]
        #
        # # passing expected parameters when linking -> `None`
        # c = p.check(self.gcc_path, "-flto -lm -ldl")
        # self.assertIsNone(c, "problem handling linker args")





if __name__ == '__main__':
    unittest.main()
