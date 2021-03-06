#!/bin/bash


# Are we on a supported distro?
source /etc/os-release
if [ "$NAME" != "CentOS Linux" ]; then 
    echo >&2 "Run this script on a CentOS host." 
    exit 1 
fi

if [[ "$EUID" -ne 0 ]]
  then echo "Please run as root"
  exit
fi

yum -y check-update
yum -yt install yum-utils 
yum -yt install https://centos7.iuscommunity.org/ius-release.rpm
yum -yt install python36u python36u-pip
sudo ln -fs /usr/bin/python3.6 /usr/bin/python3
sudo ln -fs /usr/bin/pip3.6 /usr/bin/pip3
# anytree python library
pip3 install --quiet --no-cache anytree psutil

# conditionally install sysdig
SHOULD_INSTALL_SYSDIG=1
if type "sysdig" > /dev/null 2>&1; then
  # older versions of sysdig does not have a --version flag, so use --help
  sysdig --help | grep -q "sysdig version 0.23" || SHOULD_INSTALL_SYSDIG=0
fi

if [[ "$SHOULD_INSTALL_SYSDIG" -eq 1 ]]
then
  curl -s https://s3.amazonaws.com/download.draios.com/stable/install-sysdig | bash
fi
