#!/usr/bin/env bash

set -e

SOURCE_ROOT="$( cd "$(dirname "$0")" ; pwd -P )"

pushd ${SOURCE_ROOT} &> /dev/null

if [ -f /etc/systemd/system/network-status.service ]; then
  sudo systemctl disable --now network-status
fi

sudo rm -rf \
  /usr/local/lib/network-status \
  /etc/systemd/system/network-status.service
