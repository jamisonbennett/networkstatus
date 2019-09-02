# Network status
The network status is the software for a raspberry pi project that
monitors network equipment. The hardware has status LEDs to indicate
failures in network equipment. It also has an input switch that allows
the tests to be run.

The main purpose of this project was to identify failures quickly,
especially for my wireless printer which appears to be a bug in
printer's firmware or drivers. The printer sometimes doesn't register on
the network. Rather than purchase a new printer, I created this project
to identify when the printer had failed and when it was back online. One
interesting point, is that the presence of pinging the printer seems to
significantly mitigate the failures I was seeing to the point where I
almost thought it solved the problem. The failure rate went from daily
to monthly. Although there are failures that do happen (e.g. the
printer sometimes double registers, it seems that these issues typically
automatically correct when running this network status monitor
software).

|LED Status|Meaning|
|---|---|
|Solid green|No failures in the last week|
|Mostly green with a single quick blink|No failures in the last day; but failed in the last week|
|Slow blinking green - 1 second on/off|No failures in the last hour; but failed in the last day|
|Fast blinking green|Last run passed, but failed in the last hour|
|Solid red|Last run failed|
|Off|Test schedule to run because the manual test switch was activated|
|Orange|A test is currently running|

|Input Switch|Meaning|
|---|---|
|Quick hold (0.1 seconds)|Run the normal checks|
|Long hold (3 seconds)|Run the normal and extended checks|

## Installation
1. Boot up a raspberry pi and hold SHIFT to enter recovery mode with NOOBS.
2. Select Raspbian Lite (no desktop environment)
3. Click wifi then select your wifi network and enter the password.
4. Click install
5. Allow the installation to continue
6. When the installation is complete, check OK to reboot.
7. Login with the default login "pi" and password "raspberry"
8. Change the following using `sudo raspi-config`:
   * Password
   * Timezone
   * Locale
   * Enable SSH
9. Install the software
```
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/jamisonbennett/networkstatus
./network_status/install.sh
```
10. Reboot in case there is a kernel update `sudo shutdown -r now`

## Debugging
### Manually start, stop, or check status
```
sudo systemctl start network-status
sudo systemctl stop network-status
sudo systemctl status network-status
```
### View logs
```
cat /usr/local/bin/network-status/networkstatus.log
```

## Test Approach
This was manually tested. It is meant to be test equipment to test the network, so I didn't write unit tests or integration tests.

## Hardcoded Information
There is hardcoded information because this is simply test equipment.
The following is hardcoded:
* The number of printers (it must be exactly 1)
* The external system to ping/check DNS (google.com)
