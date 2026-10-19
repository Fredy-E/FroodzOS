#!/bin/bash
# Phase 0 control-test evidence capture - run inside the Ubuntu Concept live session
# Usage: sudo bash /media/ubuntu/*/testing/control/capture.sh  (or wherever this file lives)
set -u
OUT="$(pwd)/control-evidence-$(date +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"
echo "Capturing to $OUT"
{
  echo "== date =="; date --iso-8601=seconds
  echo "== kernel =="; uname -a
  echo "== model =="; cat /proc/device-tree/model 2>/dev/null | tr -d '\0'; echo
  echo "== cpu =="; lscpu | head -15
} > "$OUT/00-basic.txt" 2>&1
dmesg > "$OUT/10-dmesg.txt" 2>&1
journalctl -b > "$OUT/20-journal.txt" 2>&1
dmidecode -t1 > "$OUT/30-dmi-system.txt" 2>&1
lspci -nnk > "$OUT/40-lspci.txt" 2>&1
lsusb > "$OUT/41-lsusb.txt" 2>&1
ip -br link > "$OUT/50-net-links.txt" 2>&1
iw dev wlan0 scan 2>/dev/null | grep -E 'SSID|freq' | head -40 > "$OUT/51-wifi-scan.txt"
for z in /sys/class/thermal/thermal_zone*; do
  echo "$z $(cat $z/type 2>/dev/null): $(cat $z/temp 2>/dev/null)"
done > "$OUT/60-thermals.txt" 2>&1
cat /sys/class/power_supply/*/capacity /sys/class/power_supply/*/status > "$OUT/61-battery.txt" 2>&1
grep -iE 'firmware|qcom|failed|ath12k|wcn|stubble|adreno|msm|soundwire|hid' "$OUT/10-dmesg.txt" > "$OUT/70-firmware-and-driver-grep.txt"
echo "Suggested manual checks (record results in control-notes.md):"
echo "  1. Display visible? brightness keys work?"
echo "  2. Built-in keyboard types? touchpad moves/scrolls?"
echo "  3. Wi-Fi sees networks incl 5GHz? wired USB network gets DHCP?"
echo "  4. Speaker test + mic test (Settings > Sound)"
echo "  5. Battery percentage visible?"
echo "  6. USB stick mounts read-write?"
echo "  7. systemctl poweroff completes cleanly? fan runs? feels hot?"
echo "CAPTURE_DONE: $OUT"
