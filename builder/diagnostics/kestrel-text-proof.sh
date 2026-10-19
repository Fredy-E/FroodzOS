#!/bin/bash
# Write only identified diagnostic state through the existing validated USB mount.
# Text diagnostic proof (startup + typed). Never starts a GUI; never blocks boot.
# helper_revision below identifies THIS helper script, NOT the UKI artifact hash.
set -u
mode=${1:-}
case "$mode" in
    startup) leaf=06-text-startup.txt; marker=KESTREL_BASH_STARTED ;;
    typed) leaf=07-typed-command.txt; marker=KESTREL_TYPED_COMMAND_OK ;;
    *) printf '%s\n' 'Expected startup or typed' >&2; exit 2 ;;
esac
state=${KESTREL_CAPTURE_STATE:-/run/kestrel-capture}
for key in destination device bootmnt; do
    [ -r "$state/$key" ] || exit 1
done
read -r dest <"$state/destination"
read -r dev <"$state/device"
read -r bootmnt <"$state/bootmnt"
read -r bid </proc/sys/kernel/random/boot_id
[ "$bootmnt" = /run/archiso/bootmnt ] || exit 1
[ "$dest" = "$bootmnt/Logs/boot-$bid" ] || exit 1
mountpoint -q "$bootmnt" || exit 1
[ "$(cat "$bootmnt/KESTREL-LOG-TARGET" 2>/dev/null)" = KESTREL_A64_USB_CAPTURE_V1 ] || exit 1
case "$(readlink -f "/sys/class/block/${dev##*/}")" in */usb[0-9]*/*) ;; *) exit 1 ;; esac
read -r pid1 </proc/1/comm
[ "$pid1" = systemd ] || { printf '%s\n' 'PID 1 is not systemd' >&2; exit 1; }
case "${KESTREL_SHELL_PID:-}" in ''|*[!0-9]*) exit 1 ;; esac
read -r shell_comm <"/proc/$KESTREL_SHELL_PID/comm" || exit 1
[ "$shell_comm" = bash ] || exit 1
fstype=$(findmnt -n -o FSTYPE /)
[ "$fstype" = overlay ] || exit 1
# Exact-token graphics request detection (test override allowed, default live).
cmdline_file=${KESTREL_CMDLINE_FILE:-/proc/cmdline}
cmdline=$(cat "$cmdline_file" 2>/dev/null || printf '')
graphics_requested=0
case " $cmdline " in *" kestrel_graphics=1 "*) graphics_requested=1 ;; esac
thermal_root=${KESTREL_THERMAL_ROOT:-/sys/class/thermal}
# Concise real SoC CPU readout: cpu*/cpuss* zones only; battery never substitutes.
# Always succeeds (exit 0) so a missing-sensor box cannot wedge the console.
# Strict decimal millidegrees: optional single leading '-', then 1-7 digits,
# nothing else. Decimal only (10#) so 08000 means 8000, never octal; the
# 7-digit bound keeps $(( )) far from 64-bit overflow. Malformed or missing
# zones are skipped and can never abort the readout (explicit return 0).
kestrel_cpu_thermal_readout() {
    found=0
    for z in "$thermal_root"/thermal_zone*; do
        [ -r "$z/type" ] && [ -r "$z/temp" ] || continue
        t=$(cat "$z/type" 2>/dev/null) || continue
        case "$t" in *battery*|*Battery*|*BATT*|*batt*) continue ;; esac
        case "$t" in cpu*|cpuss*) ;; *) continue ;; esac
        v=$(cat "$z/temp" 2>/dev/null) || continue
        sign=''
        digits=''
        case "$v" in
            -*)
                digits=${v#-}
                case "$digits" in ''|*[!0-9]*|????????*) continue ;; esac
                sign='-'
                ;;
            *)
                digits=$v
                case "$digits" in ''|*[!0-9]*|????????*) continue ;; esac
                ;;
        esac
        abs_mc=$((10#$digits)) 2>/dev/null || continue
        whole=$((abs_mc / 1000))
        frac=$(((abs_mc % 1000) / 100))
        printf '%s: %s%s.%s C (%s%s mC)\n' "$t" "$sign" "$whole" "$frac" "$sign" "$digits" 2>/dev/null || printf '%s: %s mC\n' "$t" "$v" 2>/dev/null || true
        found=1
    done
    if [ "$found" = 0 ]; then
        printf 'no_cpu_thermal_zones_found (battery never substituted)\n'
    fi
    return 0
}
temp=$(mktemp "$dest/.text-proof-XXXXXX") || exit 1
trap 'rm -f -- "$temp"' EXIT
{
    printf '%s\n' "$marker" 'helper_revision=v2-dt26 (helper identity, not UKI hash)' "mode=$mode" "boot_id=$bid" "pid1=$pid1" "fstype=$fstype" "graphics_requested=$graphics_requested"
    printf 'shell_pid=%s\nshell_comm=%s\n' "$KESTREL_SHELL_PID" "$shell_comm"
    printf 'tty='; tty
    printf 'multi_user='; systemctl is-active multi-user.target || true
    printf 'usb_logger='; systemctl is-active kestrel-usb-log.service || true
    printf '\n=== runtime modules ===\n'; cat /proc/modules
    printf '\n=== enumerated input devices (not keypress proof) ===\n'; cat /proc/bus/input/devices
    printf '\n=== cpu thermal (real SoC zones only, battery never substituted) ===\n'
    kestrel_cpu_thermal_readout || true
} >"$temp"
sync -f "$temp" || exit 1
mv -f -- "$temp" "$dest/$leaf" || exit 1
sync -f "$dest/$leaf" || exit 1
# Visible console outcome (mode-aware; text console stays text-only either way).
# Never starts a GUI here.
printf '%s\n' "$marker" "KESTREL_PROOF_SAVED $dest/$leaf"
if [ "$graphics_requested" = 1 ]; then
    printf '%s\n' 'KESTREL_MODE: graphics requested (kestrel_graphics=1). Bounded supervisor runs separately (180s session + 25s cleanup); this console stays text-only, no desktop opens here.'
else
    printf '%s\n' 'KESTREL_MODE: text-only (graphics not requested). No GUI will start; waiting only persists USB logs, it does not open a desktop.'
fi
if [ "$mode" = typed ]; then
    kestrel_cpu_thermal_readout || true
fi
