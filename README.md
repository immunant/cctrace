# cctrace
Trace invocations of compiler, linker, and other build tools.  `cctrace` relies on `sysdig` which is only supported on Linux.

## Prerequisites

On Debian hosts, run `prerequisites_deb.sh` as root. Alternatively, `sysdig` be installed by running: 

    $ curl -s https://s3.amazonaws.com/download.draios.com/stable/install-sysdig | sudo bash

Assuming pip3 is available, the `anytree` Python package can be installed via:

    $ pip3 install -U --user anytree

## Usage

`cctrace` is not a wrapper script and is intended to be run side by side (e.g. in a separate terminal) with a build command like this:

    $ sudo ./cctrace

The default policy ensures that the host compiler is used and imposes no requirements on the build flags. To enforce another policy, point `cctrace` to another policy using the `-p` command line flag. 

If the multicompiler is not installed to `$HOME/selfrando-testing/local` use the `-m` flag to specify the multicompiler install prefix or use `-a` to allow non-multicompiler tools.

`cctrace` logs all "interesting" build commands to `cctrace.log` by default. To see all options, run:

    $ sudo ./cctrace --help

## TODOs:

- [x] Handle multi-line commands 
- [x] log compiler invocations
- [x] log linker invocations
- [x] decouple core tool from multicompiler
- [ ] detect selfrando
