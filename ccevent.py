# -*- coding: utf-8 -*-

import re


def _parse_pid(s: str) -> int:
    """
    123(ab) -> 123
    """
    try:
        return int(s[:s.index('(')])
    except ValueError:  # '(' not found
        return int(s)

# def _parse_evt_args(e: dict) -> dict:
#     def split_kv(s: str) -> str:
#         try:
#             i = s.index('=')
#             return s[:i], s[i+1:]
#         except ValueError:
#             print("no = in :" + s)

#     # def parse_env(env: str) -> dict:
#     #     # base64 str -> bytes -> str
#     #     env = base64.b64decode(env).decode("utf-8")
#     #     env = [split_kv(a) for a in env.split('\x00') if a]
#     #     return {k: v for k, v in env}

#     # TODO: handle something like:
#     # 'res=61211(code) exe=/usr/share/code/code --unity-launch args= '
#     #           'tid=11013(code) pid=11013(code) ptid=1751(init) cwd= '
#     #           'fdlimit=4096 pgft_maj=146 pgft_min=61427 vm_size=1421332 '
#     #           'vm_rss=106824 vm_swap=0 comm=code '

#     args = e.pop('evt.args').rstrip().split(' ')
#     igno = ['cgroups', 'fdlimit', 'vm_size',
#             'vm_rss', 'vm_swap', 'pgft_maj', 'pgft_min']
#     args = {k: v for k, v in [split_kv(a) for a in args] if k not in igno}

#     # parse out env variables
#     # args['env'] = parse_env(args['env'])
#     if 'env' in args:
#         args.pop('env')
#     e.update(args)

#     return e        


class CCEvent(object):

    def __init__(self, tid: int, _type: str, exepath: str, pname: str,
                 pid: int, ppid: int, pargs: str, eargs: str):
        self.tid = tid
        self.type = _type
        self.exepath = exepath
        self.pname = pname
        self.pid = pid
        self.ppid = ppid
        self.pargs = pargs
        self.eargs = eargs

    @staticmethod
    def parse(line: str) -> object:
        tokens = line.split('#')
        return CCEvent(tid=_parse_pid(tokens[0]),
                    _type=tokens[1],
                    exepath=tokens[2],
                    pname=tokens[3],
                    pid=_parse_pid(tokens[4]),
                    ppid=_parse_pid(tokens[5]),
                    pargs=tokens[6],
                    eargs=tokens[7]
                    )
        