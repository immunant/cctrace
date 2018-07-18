#!/bin/bash




# Are we on a supported distro?
#dpkg-vendor --derives-from Redhat || {
#    echo >&2 "Run this script on a Centos/RHEL  host."; exit 1; 
#}

if [[ "$EUID" -ne 0 ]]
  then echo "Please run as root"
  exit
fi

yum -y check-update
yum -yt install yum-utils 
yum -yt install https://centos7.iuscommunity.org/ius-release.rpm
yum -yt install python36u python36u-pip
# anytree python library
pip3.6 install --quiet --user --no-cache anytree

# conditionally install sysdig
if ! type "sysdig" > /dev/null 2>&1; then
  # don't warn when adding developer GPG key
  curl -s https://s3.amazonaws.com/download.draios.com/stable/install-sysdig | bash
fi
