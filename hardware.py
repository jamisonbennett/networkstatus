#!/usr/bin/env python3

from enum import Enum
from networkstatus import TestObserver
import logging
import RPi.GPIO as GPIO
import time
import threading

logger = logging.getLogger(__name__)


class Hardware(TestObserver):

    class Leds(Enum):
        NORMAL_PASS = 17
        NORMAL_FAIL = 23
        EXTENDED_PASS = 24
        EXTENDED_FAIL = 25
        TEST_RUNNING = 12

    class Buttons(Enum):
        RUN_TEST = 16

    class UserInput(Enum):
        NO_INPUT = 0
        NORMAL_TEST = 1
        EXTENDED_TEST = 2

    class TestState:
        def __init__(self):
            self.normal_test_result = True
            self.extended_test_result = True
            self.scheduled_normal_test = True
            self.scheduled_extended_test = True
            self.last_normal_test_failure_time = 0
            self.last_extended_test_failure_time = 0
            self.normal_test_running = False
            self.extended_test_running = False
            self.last_normal_test_started_time = 0
            self.last_extended_test_started_time = 0

    def __init__(self):
        self.test_state_lock = threading.Lock()
        self.test_state = self.TestState()

        self.led_lock = threading.Lock()
        GPIO.setwarnings(False)
        # Blink all LEDs for 1 second
        GPIO.setmode(GPIO.BCM)
        for button in self.Buttons:
            GPIO.setup(button.value, GPIO.IN)
        for led in self.Leds:
            GPIO.setup(led.value, GPIO.OUT)
            GPIO.output(led.value, False)
        time.sleep(1)
        for led in self.Leds:
            GPIO.output(led.value, True)
        time.sleep(1)
        for led in self.Leds:
            GPIO.output(led.value, False)

    def __del__(self):
        for led in self.Leds:
            GPIO.output(led.value, False)

    def notify_test_started(self, test_type):
        """
        Update the LEDs to indicate a test is running.
        """
        self.test_state_lock.acquire()
        try:
            if test_type == TestObserver.TestType.NORMAL:
                self.test_state.normal_test_running = True
                self.test_state.last_normal_test_started_time = time.time()
            if test_type == TestObserver.TestType.EXTENDED:
                self.test_state.extended_test_running = True
                self.test_state.last_extended_test_started_time = time.time()
        finally:
            self.test_state_lock.release()
        self.__update_leds()

    def notify_test_completed(self, test_type, result):
        self.test_state_lock.acquire()
        try:
            if test_type == TestObserver.TestType.NORMAL:
                self.test_state.normal_test_result = result
                self.test_state.normal_test_running = False
                self.test_state.scheduled_normal_test = False
                if not result:
                    self.test_state.last_normal_test_failure_time = time.time()
            elif test_type == TestObserver.TestType.EXTENDED:
                self.test_state.extended_test_result = result
                self.test_state.extended_test_running = False
                self.test_state.scheduled_extended_test = False
                if not result:
                    self.test_state.last_extended_test_failure_time = time.time()
        finally:
            self.test_state_lock.release()
        self.__update_leds()

    @staticmethod
    def __get_blink_state(last_failure_time):
        current_time = time.time()
        hour = 60 * 60
        day = 24 * hour
        week = 7 * day
        if last_failure_time + hour >= current_time:
            return round(current_time * 10) % 2 > 0  # Quick blinking
        elif last_failure_time + day >= current_time:
            return round(current_time) % 2 > 0  # Slow blinking with long pause
        elif last_failure_time + week >= current_time:
            return round(current_time * 10) % 20 > 0  # Slow blinking with short pause
        else:
            return True

    def update(self):
        self.__update_leds()

    def __update_leds(self):
        current_time = time.time()
        min_test_running_led_time = 1
        self.test_state_lock.acquire()
        try:
            test_state = self.test_state
        finally:
            self.test_state_lock.release()
        normal_blink_state = Hardware.__get_blink_state(test_state.last_normal_test_failure_time)
        extended_blink_state = Hardware.__get_blink_state(test_state.last_extended_test_failure_time)
        self.led_lock.acquire()
        try:
            GPIO.output(self.Leds.NORMAL_PASS.value,
                        normal_blink_state and
                        test_state.normal_test_result and
                        not test_state.scheduled_normal_test)
            GPIO.output(self.Leds.NORMAL_FAIL.value,
                        not test_state.normal_test_result and
                        not test_state.scheduled_normal_test)
            GPIO.output(self.Leds.EXTENDED_PASS.value,
                        extended_blink_state and
                        test_state.extended_test_result and
                        not test_state.scheduled_extended_test)
            GPIO.output(self.Leds.EXTENDED_FAIL.value,
                        not test_state.extended_test_result and
                        not test_state.scheduled_extended_test)
            GPIO.output(self.Leds.TEST_RUNNING.value,
                        test_state.normal_test_running or
                        test_state.extended_test_running or
                        test_state.last_normal_test_started_time + min_test_running_led_time >= current_time or
                        test_state.last_extended_test_started_time + min_test_running_led_time >= current_time)
        finally:
            self.led_lock.release()

    def get_user_input(self, timeout):
        sleep_time = 0.1
        button_push_time_for_extended_test = 3
        timeout_time = time.time() + timeout
        user_input_time = None
        while True:
            if user_input_time is None and GPIO.input(self.Buttons.RUN_TEST.value):
                # Initial button push
                user_input_time = time.time()
                self.test_state_lock.acquire()
                try:
                    self.test_state.scheduled_normal_test = True
                finally:
                    self.test_state_lock.release()
                self.__update_leds()
            elif user_input_time is not None and not GPIO.input(self.Buttons.RUN_TEST.value):
                # Button was pushed and released before the extended test time was reached
                return self.UserInput.NORMAL_TEST
            elif user_input_time is not None and time.time() >= user_input_time + button_push_time_for_extended_test:
                # Button was held for the extended test time
                self.test_state_lock.acquire()
                try:
                    self.test_state.scheduled_extended_test = True
                finally:
                    self.test_state_lock.release()
                self.__update_leds()
                return self.UserInput.EXTENDED_TEST
            elif user_input_time is None and time.time() >= timeout_time:
                # The button was not pushed and the timeout has happened
                return self.UserInput.NO_INPUT
            else:
                time.sleep(sleep_time)

