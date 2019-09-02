#!/usr/bin/env bash

set -e

SOURCE_ROOT="$( cd "$(dirname "$0")" ; pwd -P )"

pushd ${SOURCE_ROOT} &> /dev/null

./uninstall.sh

sudo apt-get update
sudo apt-get dist-upgrade -y
sudo apt-get autoremove -y
sudo apt-get install -y \
  python3-pip \
  avahi-utils
pip3 install virtualenv

# Add $HOME/.local/bin to the environment (for python)
source ${HOME}/.profile

virtualenv venv
source venv/bin/activate
pip3 install -r requirements.txt
deactivate

sudo apt-get autoremove --purge -y

rm -rf /usr/local/lib/network-status
sudo mkdir -p /usr/local/bin/network-status
sudo cp -r \
  venv \
  *.py \
  networkstatus.sh \
  network-status-service.sh \
  network-status.service \
  /usr/local/bin/network-status/
sudo ln -s /usr/local/bin/network-status/network-status.service /etc/systemd/system/

sudo systemctl enable systemd-networkd-wait-online
sudo systemctl enable avahi-daemon
sudo systemctl enable network-status
