#!/bin/bash

set -e

export DEBIAN_FRONTEND=noninteractive  

# Are we on a supported distro?
dpkg-vendor --derives-from Debian || {
    echo >&2 "Run this script on a Debian/Ubuntu host."; exit 1; 
}

if [[ "$EUID" -ne 0 ]]
  then echo "Please run as root"
  exit
fi

apt-get -qq update
apt-get -qq install build-essential curl htop python3-pip ipython3
# anytree python library
pip3 install --quiet --user --no-cache anytree

# conditionally install sysdig
SHOULD_INSTALL_SYSDIG=1
if type "sysdig" > /dev/null 2>&1; then
  # older versions of sysdig does not have a --version flag, so use --help
  sysdig --help | grep -q "sysdig version 0.23" || SHOULD_INSTALL_SYSDIG=0
fi

if [[ "$SHOULD_INSTALL_SYSDIG" -eq 1 ]]
then
  # don't warn when adding developer GPG key
  export APT_KEY_DONT_WARN_ON_DANGEROUS_USAGE=1
  curl -s https://s3.amazonaws.com/download.draios.com/stable/install-sysdig | bash
fi
