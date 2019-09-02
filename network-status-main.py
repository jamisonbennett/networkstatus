#!/usr/bin/env python3

import datetime
import logging
from hardware import Hardware
import networkstatus
import time
import threading

logger = logging.getLogger(__name__)


def update(hardware, update_interval):
    while True:
        hardware.update()
        time.sleep(update_interval)


def main():
    hardware = Hardware()
    update_interval = 0.1
    thread = threading.Thread(target=update, args=(hardware, update_interval), daemon=True)
    thread.start()
    user_input_timeout = 1
    status_timeout = 10
    max_ping = 200
    quick_checks = networkstatus.MultipleChecks([
        networkstatus.PingDefaultGatewayCheck(max_ping=max_ping, timeout=status_timeout),
        networkstatus.PingCheck('google.com', max_ping=max_ping, timeout=status_timeout),
        networkstatus.DnsCheck('google.com', timeout=status_timeout),
        networkstatus.PingPrinterCheck(max_ping=max_ping, timeout=status_timeout)
    ])
    extended_checks = networkstatus.MultipleChecks([
        networkstatus.SpeedCheck(
            min_down=20*1000*1000,  # 20 mpbs (limited by Raspberry Pi 3b wifi capabilities)
            min_up=5*1000*1000,  # 5 mpbs
            max_ping=max_ping,
            timeout=status_timeout)
    ])
    checks = networkstatus.NormalAndExtendedChecks(quick_checks, extended_checks, [hardware])

    # Start by running the extended test
    last_normal_test = 0
    last_extended_test = 0

    normal_test_interval = 60
    extended_test_interval = 60 * 60

    while True:
        current_time = time.time()
        if (current_time >= last_normal_test + normal_test_interval or
           current_time >= last_extended_test + extended_test_interval):
            last_normal_test = current_time
            time_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if current_time >= last_extended_test + extended_test_interval:
                print('# time(utc),{}'.format(checks.column_names()))
                last_extended_test = current_time
                result_str = checks.extended_check()
            else:
                result_str = checks.normal_check()
            print('{},{}'.format(time_str, result_str), flush=True)
        user_input = hardware.get_user_input(user_input_timeout)
        if user_input == hardware.UserInput.NORMAL_TEST:
            last_normal_test = 0
        elif user_input == hardware.UserInput.EXTENDED_TEST:
            last_normal_test = 0
            last_extended_test = 0


if __name__ == "__main__":
    main()
