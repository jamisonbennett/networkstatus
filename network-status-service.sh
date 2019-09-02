#!/usr/bin/env bash

BIN_ROOT="$( cd "$(dirname "$0")" ; pwd -P )"

pushd ${BIN_ROOT}

start() {
  ./networkstatus.sh &
}

stop() {
  pkill -f network-status-main.py
}

case $1 in
  start|stop) "$1" ;;
esac
