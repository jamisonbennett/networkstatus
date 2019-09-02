#!/usr/bin/env python3

import dns.resolver
from enum import Enum
import functools
import json
import logging
import re
import speedtest
import subprocess


logger = logging.getLogger(__name__)


class TestObserver:

    class TestType(Enum):
        NORMAL = 1
        EXTENDED = 2

    def notify_test_started(self, test_type):
        return

    def notify_test_completed(self, test_type, result):
        return


def external_command(args, input_str=None, throw_of_error=True, timeout=10):
    """
    Run an external command with a timeout

    :param args: The arguments for popen
    :param input_str: The input text
    :param throw_of_error: Whether to throw an exception if the program exits with an error code
    :param timeout: The timeout in seconds
    :return: (standard out, standard error, error code)
    """
    p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8')
    (out, err) = p.communicate(input_str, timeout=timeout)
    if throw_of_error and p.returncode != 0:
        raise Exception('Command {} failed with code {}. {}'.format(args[0], p.returncode, err))
    return out, err, p.returncode


def ping(host, timeout=10):
    """
    Ping a host

    :param host: The host to ping
    :param timeout: The timeout in seconds
    :return: The time in milliseconds
    """
    out, _, _ = external_command(args=['ping', '-c', '1', '-w', str(timeout), host], timeout=timeout)
    time_string = re.search('time=(.*) ms', out).group(1)
    time = float(time_string)
    return time


def dns_resolve(host, timeout=10):
    """
    Get the IPv4 address of the host

    :param host: The host to lookup
    :param timeout: The timeout in seconds
    :return: The IPv4 address
    """
    answers = dns.resolver.query(host, lifetime=timeout)
    ipv4 = answers[0].address
    return ipv4


def default_gateway(timeout=10):
    """
    Get the IPv4 default gateway

    :param timeout: The timeout in seconds
    :return: The IPv4 address
    """
    out, _, _ = external_command(args=['ip', '-j', '-4', 'route'], timeout=timeout)
    for record in json.loads(out):
        if record['dst'] == 'default':
            return record['gateway']
        continue
    raise Exception('No default route')


def dns_service_discovery(service_type, timeout=10):
    """
    Use DNS-SD to get records

    :param service_type: The DNS-SD type
    :param timeout: The timeout in seconds
    :return: [dict(name, address)] The records
    """
    out, _, _ = external_command(
        args=['avahi-browse', '-d', 'local', '-r', '-t', '-p', '-k', service_type],
        timeout=timeout)
    list_with_duplicates = []
    for record in out.splitlines():
        record = record.split(';')
        if record[0] != '=':
            continue
        list_with_duplicates += [dict(
            name=record[3],
            address=record[7]
        )]

    ret = [dict(t) for t in {tuple(d.items()) for d in list_with_duplicates}]  # Remove duplicates
    return ret


def discover_printers(timeout=10):
    """
    Use DNS-SD to discovery the printers

    :param timeout: The timeout in seconds
    :return: [dict(name, address)] The records
    """
    return dns_service_discovery('_pdl-datastream._tcp', timeout=timeout)


class StatusCheck:
    """
    An interface for checking the equipment status
    """

    def do_to_value(self, value_string):
        """
        Runs the status check and returns the result string.
        :value_string: The string to convert to teh value
        :return: The result of the evaluation criteria (None, True, False)
        """
        return None

    def do_check(self):
        """
        Runs the status check and returns the result string.
        :return: The result string (CSV)
        """
        return ""

    def check(self):
        """
        Runs the status check and returns the result string.
        :return: Tuple where [0] The result string (CSV) and [1] is an array with the result with evaluation criteria
        applied (None, True, False))
        """
        value = self.do_check()
        return value, [self.do_to_value(value)]

    def column_names(self):
        """
        Gets the column names
        :return: The column names
        """
        return ""

    def num_columns(self):
        """
        Gets the number of columns
        :return: The number of columns
        """
        return 1


class FailEveryNTimes(StatusCheck):
    """
    Test class that fails every N times
    """

    PASS = "Pass"
    FAIL = "Fail"

    def __init__(self, n):
        self.n = n
        self.i = n

    def do_to_value(self, value_string):
        return value_string != self.FAIL

    def do_check(self):
        self.i = self.i - 1
        if self.i == 0:
            self.i = self.n
            return self.FAIL
        return self.PASS

    def column_names(self):
        return 'fail every {} times'.format(self.n)


class PingCheckBase(StatusCheck):
    """
    Base class for ping checks
    """

    NO_PING = "-1"

    def __init__(self, max_ping, timeout):
        self.max_ping = max_ping
        self.timeout = timeout

    def do_to_value(self, value_string):
        if value_string == self.NO_PING:
            return False
        return float(value_string) <= self.max_ping


class PingPrinterCheck(PingCheckBase):
    """
    Performs the printer status check
    """

    def __init__(self, max_ping, timeout):
        PingCheckBase.__init__(self, max_ping, timeout)

    def do_to_value(self, value_string):
        raise NotImplementedError

    def do_check(self):
        try:
            printers = discover_printers(timeout=self.timeout)
            printer_addresses = ' '.join([p['address'] for p in printers])
            if len(printers) == 0:
                raise Exception('No printer found.')
            if len(printers) > 1:
                logger.error('Multiple printers found, cannot resolve to a unique printer. '
                             'The following printers were found: {}.'.format(str(printers)))
                return '{},{}'.format(self.NO_PING, printer_addresses)
            printer = printers[0]
            return '{},{}'.format(ping(printer['address']), printer_addresses)
        except Exception as e:
            logger.error("Failed to ping the printer. {}".format(e))
            return self.NO_PING + ","

    def check(self):
        value = self.do_check()
        values = value.split(",")
        return value, [PingCheckBase.do_to_value(self, values[0]), None]

    def column_names(self):
        return "ping time for the printer (ms),printer address"

    def num_columns(self):
        return 2


class PingCheck(PingCheckBase):
    """
    Pings a host
    """

    def __init__(self, host, max_ping, timeout):
        PingCheckBase.__init__(self, max_ping, timeout)
        self.host = host

    def do_check(self):
        try:
            return str(ping(self.host, timeout=self.timeout))
        except Exception as e:
            logger.error("Failed to ping {}. {}".format(self.host, e))
            return "-1"

    def column_names(self):
        return "ping time for {} (ms)".format(self.host)


class PingDefaultGatewayCheck(PingCheckBase):
    """
    Pings the default gateway
    """

    def __init__(self, max_ping, timeout):
        PingCheckBase.__init__(self, max_ping, timeout)

    def do_check(self):
        try:
            default_gw = default_gateway(self.timeout)
            return str(ping(default_gw, timeout=self.timeout))
        except Exception as e:
            logger.error("Failed to ping the default gateway. {}".format(e))
            return "-1"

    def column_names(self):
        return "ping time for the default gateway (ms)"


class DnsCheck(StatusCheck):
    """
    Checks DNS resolution for a host
    """

    def __init__(self, host, timeout):
        self.host = host
        self.timeout = timeout

    def do_to_value(self, value_string):
        bool(value_string)

    def do_check(self):
        try:
            dns_resolve(self.host, timeout=self.timeout)
            return "True"
        except Exception as e:
            logger.error("Failed to resolve DNS for {}. {}".format(self.host, e))
            return "False"

    def column_names(self):
        return "DNS resolution check for {}".format(self.host)


class SpeedCheck(StatusCheck):
    """
    Checks network speed
    """

    def __init__(self, min_down, min_up, max_ping, timeout):
        self.min_down = min_down
        self.min_up = min_up
        self.max_ping = max_ping
        self.timeout = timeout

    def do_to_value(self, value_string):
        raise NotImplementedError

    def do_check(self):
        raise NotImplementedError

    def check(self):
        try:
            speed_tester = speedtest.Speedtest(timeout=self.timeout)
            server = speed_tester.get_best_server()
            down = speed_tester.download()
            up = speed_tester.upload()
            name = server['name'].replace(',', '')
            latency = server['latency']
            results = [
                down >= self.min_down,
                up >= self.min_up,
                latency <= self.max_ping,
                None
            ]
            return "{},{},{},{}".format(round(down), round(up), latency, name), results
        except Exception as e:
            logger.error("Failed to run the speed test. {}".format(e))
            return "-1,-1,-1,N/A", [False, False, False, None]

    def column_names(self):
        return "download speed (bps),upload speed (bps),speed test latency (ms),speed test server name"

    def num_columns(self):
        return 4


def combine_checks(array_of_tuples):
    """
    Combines multiple checks into a single check

    :param array_of_tuples: An array of tuples where tuple element 0 is the string result and tuple element 1 is the
    array of the evaluation criteria (True, False, or None)
    :return: Tuple where [0] The result string (CSV) and [1] is an array with the result with evaluation criteria
    applied (None, True, False))
    """
    result_strings = [r[0] for r in array_of_tuples]
    result_arrays = [r[1] for r in array_of_tuples]
    result_string = ','.join(result_strings)
    result_array = [element for inner_array in result_arrays for element in inner_array]
    return result_string, result_array


class MultipleChecks(StatusCheck):
    """
    Runs several checks
    """

    def __init__(self, checks):
        self.checks = checks

    def do_to_value(self, value_string):
        raise NotImplementedError

    def do_check(self):
        raise NotImplementedError

    def check(self):
        return combine_checks([check.check() for check in self.checks])

    def column_names(self):
        return ','.join([check.column_names() for check in self.checks])

    def num_columns(self):
        return sum([check.num_columns() for check in self.checks])


def combine_results(lhs, rhs):
    if lhs is None:
        return rhs
    if rhs is None:
        return lhs
    return lhs and rhs


class NormalAndExtendedChecks:
    """
    Runs some checks all the time and other are only run when requested.
    """

    def __init__(self, normal_checks, extended_checks, test_observers):
        self.normal_checks = normal_checks
        self.extended_checks = extended_checks
        self.test_observers= test_observers

    def normal_check(self):
        """
        Run the normal checks
        :return: the result string
        """
        skip_extended = (
            ','.join([""] * self.extended_checks.num_columns())
        )
        for observer in self.test_observers:
            observer.notify_test_started(TestObserver.TestType.NORMAL)
        results = self.normal_checks.check()
        normal_tests_result = functools.reduce(combine_results, results[1], None)
        for observer in self.test_observers:
            observer.notify_test_completed(TestObserver.TestType.NORMAL, normal_tests_result)
        return results[0] + "," + skip_extended

    def extended_check(self):
        """
        Run the normal checks and extended checks
        :return: the result string
        """
        normal_results = self.normal_checks.check()
        for observer in self.test_observers:
            observer.notify_test_started(TestObserver.TestType.NORMAL)
            observer.notify_test_started(TestObserver.TestType.EXTENDED)
        normal_tests_result = functools.reduce(combine_results, normal_results[1], None)
        extended_results = self.extended_checks.check()
        extended_tests_result = functools.reduce(combine_results, extended_results[1], None)
        for observer in self.test_observers:
            observer.notify_test_completed(TestObserver.TestType.NORMAL, normal_tests_result)
            observer.notify_test_completed(TestObserver.TestType.EXTENDED, extended_tests_result)
        return normal_results[0] + "," + extended_results[0]

    def column_names(self):
        normal_column_names = self.normal_checks.column_names()
        extended_column_names = self.extended_checks.column_names()
        return normal_column_names + "," + extended_column_names

    def num_columns(self):
        return self.normal_checks.num_columns() + self.extended_checks.num_columns()
