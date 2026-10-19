#!/bin/bash
# Label for the display-subsystem node.
grep -n -E '^\s*[a-z0-9_]+:\s*display-subsystem@ae00000' /home/builder/boot-failure-tests/slim3.dts | head -3
