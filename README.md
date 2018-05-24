# cctrace
Trace invocations of compiler, linker, and other build tools.

Note: `cctrace` relies on `sysdig` which is only fully supported on Linux.

## TODOs:

- [ ] Handle multi-line commands 
- [ ] Improve classification of tools
    - [ ] detect non-system compilers
    - [ ] detect selfrando
- [ ] Print process tree    