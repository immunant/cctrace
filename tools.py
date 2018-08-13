import os
import re
from enum import Enum



# _host_util_re = re.compile(r"/(usr/)?bin/.*")
# _build_tool_re = re.compile(
#     r"[^\0]+/((c|cc|g|q)?make|cpack|ctest|scons|ninja|bear|ccache|libtool)")
# _gcc_lib_re = re.compile(
#     r"/usr/lib/gcc/[^\0]+/(\d\.\d|\d)/(cc(1|1plus)|collect2)")
# _gcc_bin_re = re.compile(
#     r"/usr/bin/(x86_64|i686|arm|arm64|aarch64)-linux-gnu-")
# _llvm_lib_re = re.compile(r"/usr/lib/llvm-[\d\.]+/bin/clang(\+\+)?")
# # binaries that are likely compiler drivers
# _compiler_driver_re = re.compile(
#     r"[^\0]+/(clang(\+\+)?|gcc|g\+\+|suncc|icc|cc|c\+\+)$")
# _linker_re = re.compile(r"[^\0]+/ld(\.gold|\.bfd|\.ldd)?$")

class ToolType(Enum):
    CCompiler = "cc",
    CXXCompiler = "c++",
    GCCHelper = "<gcc_helper>",
    LLVMHelper = "<llvm_helper>",
    Linker = "ld",
    Archiver = "ar",
    Indexer = "ranlib",
    Lister = "nm",
    Builder = "<builder>",
    Interpreter = "<interpreter>",
    Unknown = "<unknown>",

    def __str__(self):
        return self.value[0]

    def __repr__(self):
        return self.value[0]





def get_tool_type(exepath: str) -> ToolType:
    """
    >>> get_tool_type("/no/such/tool")
    <unknown>
    >>> get_tool_type("/usr/bin/cc")
    cc
    >>> get_tool_type("/usr/bin/clang")
    cc
    >>> get_tool_type("/usr/bin/gcc")
    cc
    """
    type_ = get_tool_type.cache.get(exepath, None)
    if type_:
        return type_

    name = os.path.basename(exepath)

    for (type_, matcher) in get_tool_type.matchers.items():
        if matcher.match(name):
            get_tool_type.cache[exepath] = type_
            return type_

    return ToolType.Unknown


get_tool_type.cache = dict()  # init cache
get_tool_type.matchers = {k: re.compile(v) for (k, v) in {
    ToolType.CCompiler: r"(clang|gcc|suncc|icc|cc)$",
    ToolType.CXXCompiler: r"(clang\+\+|g\+\+|c\+\+)$",
    ToolType.GCCHelper: ""
    ToolType.Linker: r"ld(\.gold|\.bfd|\.ldd)?$",
    ToolType.Interpreter: r"(python|ruby|tclsh|perl|lua)[\d\.]*$",

}.items()}


if __name__ == "__main__":
    import doctest
    doctest.testmod()
