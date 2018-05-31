# cctrace
Trace invocations of compiler, linker, and other build tools.

Note: `cctrace` relies on `sysdig` which is only fully supported on Linux.

## Prerequisites

```sh
curl -s https://s3.amazonaws.com/download.draios.com/stable/install-sysdig | sudo bash
```

## TODOs:

- [x] Handle multi-line commands 
- [ ] Improve classification of tools
    - [ ] detect non-system compilers
    - [ ] detect selfrando
- [ ] Print process tree    