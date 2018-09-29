import os
import re
import subprocess as sp
from enum import Enum

class ToolType(Enum):
    c_compiler = 1
    cxx_compiler = 2
    gcc_lib = 3
    gcc_bin = 4
    llvm_lib = 5
    linker = 6
    archiver = 7  # ar
    indexer = 8  # ranlib
    sym_lister = 9  # nm
    builder = 10  # make, cmake, etc.
    interpreter = 11
    util = 12
    assembler = 13
    unknown = 14

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    @staticmethod
    def from_path(exepath: str):
        """

        >>> ToolType.from_path("/no/such/tool")
        unknown
        >>> ToolType.from_path("/usr/bin/cc")
        c_compiler
        >>> ToolType.from_path("/usr/bin/clang")
        c_compiler
        >>> ToolType.from_path("/usr/bin/gcc")
        c_compiler
        >>> ToolType.from_path("/usr/bin/python3")
        interpreter
        >>> ToolType.from_path("/usr/bin/python3.6")
        interpreter
        >>> ToolType.from_path("/usr/bin/python2")
        interpreter
        >>> ToolType.from_path("/usr/bin/tclsh8.6")
        interpreter
        >>> ToolType.from_path("/bin/grep")
        util
        """
        typ = ToolType._cache.get(exepath, None)
        if typ:
            return typ

        for (typ, matcher) in ToolType._matchers.items():
            if matcher.match(exepath):
                ToolType._cache[exepath] = typ
                return typ

        return ToolType.unknown

    def is_compiler(self):
        return self == ToolType.c_compiler or self == ToolType.cxx_compiler

    def is_compiler_or_linker(self):
        if self == ToolType.linker:
            return True
        else:
            return self.is_compiler()

    def is_compiler_helper(self):
        return self == ToolType.gcc_bin or \
               self == ToolType.gcc_lib or \
               self == ToolType.llvm_lib


ToolType._cache = dict()  # init cache
ToolType._matchers = {k: re.compile(v) for (k, v) in {
    ToolType.c_compiler: r"[^\0]+/(clang|gcc|suncc|icc|cc)$",
    ToolType.cxx_compiler: r"[^\0]+/(clang\+\+|g\+\+|c\+\+)$",
    ToolType.gcc_lib: r"/usr/lib/gcc/[^\0]+/(\d\.\d|\d)/(cc(1|1plus)|collect2)",
    ToolType.gcc_bin: r"/usr/bin/(x86_64|i686|arm|arm64|aarch64)-linux-gnu-",
    ToolType.llvm_lib: r"/usr/lib/llvm-[\d\.]+/bin/clang(\+\+)?",
    ToolType.linker: r"[^\0]+/ld(\.gold|\.bfd|\.ldd)?$",
    ToolType.interpreter: r"[^\0]+/(python|ruby|tclsh|perl|lua)[\d\.]*$",
    ToolType.builder: r"[^\0]+/((c|cc|g|q)?make|cpack|ctest|scons|ninja|bear|ccache|libtool)",
    ToolType.util: r"/(usr/)?bin/.*",
}.items()}


def get_tool_ver(exepath: str):
    """
    Query and cache tool version. Some tools are ignored.
    """
    version = get_tool_ver.cache.get(exepath, None)
    if version:
        return version

    # TODO: special case bear? old versions only support -v, 
    # new versions only support --version.
    if exepath == "/usr/bin/bear":
        return None

    tt = ToolType.from_path(exepath)
    if tt == ToolType.unknown or tt == ToolType.util:
        return None

    # NOTE: skipping this step leads to prettier version output for GCC
    # at the expense of additional cache entries.
    # exepath = os.path.realpath(exepath)  # canonicalize path
    try:
        p = sp.Popen([exepath, '--version'], stdout=sp.PIPE, stderr=sp.PIPE)
        stdout, stderr = p.communicate()
        ver = stdout.split(b'\n', 1)[0]  # get first line
        # print("{} -> {}".format(exepath, ver))
        ver = ver.decode()  # bytes -> str
        ver = re.sub(r"\s\(.*\)", "", ver)  # remove parenthetical info if any
        get_tool_ver.cache[exepath] = ver
        return ver
    except OSError:
        get_tool_ver.cache[exepath] = ""
        return ""


get_tool_ver.cache = dict()  # init cache


def get_unchecked_tools(p):
    # return all the tools that are not checked under the policy
    unchecked = [(ToolType.from_path(k), k)
                 for k in get_tool_ver.cache.keys()
                 if not p.is_checked(k)]
    return sorted(unchecked, key=lambda t: t[0].value)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
