# cctrace
Trace invocations of compiler, linker, and other build tools. `cctrace` depends on [`sysdig`](https://github.com/draios/sysdig) for Linux.

## Prerequisites

On Debian hosts, run `prerequisites_deb.sh` as root. Alternatively, install `sysdig` by running: 

    $ curl -s https://s3.amazonaws.com/download.draios.com/stable/install-sysdig | sudo bash

Assuming pip3 is available, the `anytree` Python package can be installed via:

    $ pip3 install -U --user anytree

## Usage

`cctrace` is not a wrapper script around build systems. It is instead intended to be run side by side (e.g. in a separate terminal) with a build command like this:

    $ sudo ./cctrace

The default policy ensures that the host compiler is used and imposes no requirements on the build flags. To enforce another policy, point `cctrace` to a custom policy using the `-p` command line flag. 

`cctrace` logs all "interesting" build commands to `cctrace.log` by default. To see all options, run:

    $ sudo ./cctrace --help

## Policies

`cctrace` policies are stored as JSON files. See `policy/default.cctrace.json` for an example.
The top-level configuration items are:

- `name`: names the policy (string)
- `keep_going`: stop on policy violation or not (bool)
- `c_compiler`: configures the C compiler. Subkeys:
    - `path`: string or list of strings of expected paths
    - `args`: list of strings of expected arguments
    - `compile_args`: list of strings of *additional* arguments when compiler is *not* linking.
    - `link_args`: list of strings of *additional* arguments when compiler is linking.
- `cxx_compiler`: configures the C++ compiler. Same subkeys as `c_compiler`.
- `linker`: configures the linker. Subkeys `path` and `args` same format as `c_compiler`.
- `assembler`: configures the assembler (`as`, `yasm`, `nasm`) same subkeys as linker.
- `archiver`: configures the archiver (`ar`) same subkeys as linker.
- `indexer`: configures the indexer (`ranlib`) same subkeys as linker.
- `sym_lister`: configures the symbol lister (`nm`) same subkeys as linker.

## Acknowledgement and Disclaimer
This material is based upon work supported by the United States Air Force and DARPA under Contract No. FA8750-15-C-0124.
Any opinions, findings and conclusions or recommendations expressed in this material are those of the author(s) and do not necessarily reflect the views of the United States Air Force and DARPA.
Distribution Statement A, “Approved for Public Release, Distribution Unlimited.”
