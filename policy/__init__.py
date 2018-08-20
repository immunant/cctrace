import os
import sys
import json
import argparse
import logging

from itertools import chain

from tools import ToolType

# TODO: avoid duplicating this class
class Colors:
    # Terminal escape codes
    DGRAY = '\033[90m'
    LRED = '\033[91m'
    LGREEN = '\033[92m'
    LYELLOW = '\033[93m'
    LBLUE = '\033[94m'
    LMAGENTA = '\033[95m'
    LCYAN = '\033[96m'
    NO_COLOR = '\033[0m'


class PolicyError(object):
    def __init__(self, message, tt, expected, observed):
        self.tt = tt
        self.message = message
        self.expected = expected
        self.observed = observed

    @staticmethod
    def argument_mismatch(tt, expected, observed):
        message = "missing argument to {}."
        message = message.format(tt.name)
        return PolicyError(message, tt, expected, observed)

    @staticmethod
    def tool_mismatch(tt, expected, observed):
        message = "not using expected {}."
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
    tools = [ToolType.c_compiler, ToolType.cxx_compiler, ToolType.linker]
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
        self._path_expect = dict()  # type: dict[ToolType, str]
        self._args_expect = dict()  # type: dict[ToolType, list[str]]
        self._compile_args_expect = dict()  # type: dict[ToolType, list[str]]
        self._link_args_expect = dict()  # type: dict[ToolType, list[str]]

    def update(self, args: argparse.Namespace) -> None:

        pol_file = json.load(args.policy)  # type: dict

        # type check top-level elements of policy file
        for (k, v) in pol_file.items():
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
            tool_cfg = pol_file.pop(t.name, None)  # type: dict
            if tool_cfg:
                # paths
                path = tool_cfg.pop("path", None)  # type: str
                path = os.path.expanduser(path)
                if path:
                    if type(path) != str:
                        emsg = "Error, path key must be a string, was "
                        emsg += path.__class__.__name__
                        sys.exit(emsg)
                    if not os.path.exists(path):
                        emsg = "Error, couldn't find {} at {}"
                        emsg = emsg.format(t.name, path)
                        sys.exit(emsg)
                    canon_path = os.path.realpath(path)  # canonicalize
                    self._path_expect[t] = canon_path

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
                        self._compile_args_expect[t] = targs

                # did we process all configuration keys for t?
                if len(tool_cfg):
                    logging.warning("didn't understand policy for %s", t.name)

        self.name = pol_file.pop("name", self.name)
        self.keep_going = pol_file.pop("keep_going", self.keep_going)

    def check(self, exepath: str, args: str = "") -> PolicyError:
        tt = ToolType.from_path(exepath)  # type: ToolType

        def check_args(expected_args) -> None:
            if expected_args:
                for expected in expected_args:
                    if expected not in args:
                        return PolicyError.argument_mismatch(tt, 
                                                             expected, 
                                                             args)

        expected_args = self._args_expect.get(tt, None)
        check_args(expected_args)

        if tt.is_compiler():
            if " -c " in args:
                expected_args = self._compile_args_expect.get(tt, None)
                check_args(expected_args)
            else:
                expected_args = self._link_args_expect.get(tt, None)
                check_args(expected_args)

        expected_path = self._path_expect.get(tt, None)
        observed_path = os.path.realpath(exepath)
        if expected_path and expected_path != observed_path:
            return PolicyError.tool_mismatch(tt, expected_path, observed_path)

        return None

    def is_checked(self, exepath: str) -> bool:
        tt = ToolType.from_path(exepath)  # type: ToolType
        return tt in self._path_expect or tt in self._args_expect


policy = Policy()
