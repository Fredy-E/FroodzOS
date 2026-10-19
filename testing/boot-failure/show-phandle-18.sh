#!/bin/bash
# What node owns line 300's phandle?
DTS=/home/builder/boot-failure-tests/slim3.dts
sed -n '285,305p' "$DTS"
