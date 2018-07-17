# cctrace
Trace invocations of compiler, linker, and other build tools.  `cctrace` relies on `sysdig` which is only supported on Linux.

## Prerequisites

On Debian hosts, run `prerequisites_deb.sh` as root. Alternatively, `sysdig` be installed by running: 

    $ curl -s https://s3.amazonaws.com/download.draios.com/stable/install-sysdig | sudo bash

Assuming pip3 is available, the `anytree` Python package can be installed via:

    $ pip3 install -U --user anytree

## TODOs:

- [x] Handle multi-line commands 
- [x] log compiler invocations
- [x] log linker invocations
- [ ] detect selfrando
- [ ] decouple core tool from multicompiler