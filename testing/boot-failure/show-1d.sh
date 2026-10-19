#!/bin/bash
# Node owning phandle 0x1d (line 7706) = the bcm voter device.
sed -n '7695,7710p' /home/builder/boot-failure-tests/slim3.dts
