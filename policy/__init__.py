import json
import argparse

from tools import ToolType

class Policy(object):


    def __init__(self):
        self.name = "default"
        self.keep_going = False
        self.config = dict()

    def update(self, args: argparse.Namespace) -> None:

        cfg = json.load(args.config)
        self.name = cfg.pop("name", self.name)
        self.keep_going = cfg.pop("keep_going", self.keep_going)
        self.config = cfg

        # TODO: check that all referenced tools exist

    def check(self, exepath: str):
        pass

    def passed_check(self, exepath: str):
        # todo: implement
        return False

policy = Policy()
