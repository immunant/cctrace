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
apt-get install -qq build-essential htop
# don't warn when adding developer GPG key
export APT_KEY_DONT_WARN_ON_DANGEROUS_USAGE=1

# conditionally install sysdig
if ! type "sysdig" > /dev/null 2>&1; then
  curl -s https://s3.amazonaws.com/download.draios.com/stable/install-sysdig | bash
fi
