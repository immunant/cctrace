import os
import sys
import json
import argparse
import logging

from itertools import chain

from tools import ToolType


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
        self._path_expect: dict[ToolType, str] = dict()
        self._args_expect: dict[ToolType, list[str]] = dict()

    def update(self, args: argparse.Namespace) -> None:

        cfg: dict = json.load(args.config)

        # type check top-level elements of policy file
        for (k, v) in cfg.items():
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
            tool_cfg: dict = cfg.pop(t.name, None)
            if tool_cfg:
                # paths
                path: str = tool_cfg.pop("path", None)
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

                targs: list[str] = tool_cfg.pop("args", None)
                if targs:
                    if type(targs) != list:
                        emsg = "Error, args key must be a list of strings, was "
                        emsg += targs.__class__.__name__
                        sys.exit(emsg)
                    self._args_expect[t] = targs

                # did we process all configuration keys for t?
                if len(tool_cfg):
                    logging.warning("didn't understand policy for %s", t.name)

        self.name = cfg.pop("name", self.name)
        self.keep_going = cfg.pop("keep_going", self.keep_going)

    def check(self, exepath: str, args: list = None) -> (bool, str, ToolType):
        tt: ToolType = ToolType.from_path(exepath)

        expected_args = self._args_expect.get(tt, None)
        if expected_args:
            # TODO: handle argument expectations
            assert False, "not implemented. args: " + str(args)

        expected_path = self._path_expect.get(tt, None)
        observed_path = os.path.realpath(exepath)
        if expected_path:
            return expected_path == observed_path, expected_path, tt


        return True, None, tt

    def is_checked(self, exepath: str) -> bool:
        tt: ToolType = ToolType.from_path(exepath)
        return tt in self._path_expect or tt in self._args_expect


policy = Policy()
