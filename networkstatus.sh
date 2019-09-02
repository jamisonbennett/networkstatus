#!/usr/bin/env bash

set -e

BIN_ROOT="$( cd "$(dirname "$0")" ; pwd -P )"

pushd ${BIN_ROOT} &> /dev/null

source venv/bin/activate
./network-status-main.py &>> networkstatus.log

