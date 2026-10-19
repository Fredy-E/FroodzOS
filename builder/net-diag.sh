#!/bin/bash
# HISTORICAL NETWORK REPRODUCER, NOT A CURRENT SETUP SCRIPT.
# Network constants are documentation-only redactions. Do not use as-is.
if [ "${FROODZOS_ALLOW_HISTORICAL_NETWORK:-0}" != 1 ]; then
    printf '%s\n' 'Refusing archived network changes; inspect and adapt in an isolated builder only' >&2
    exit 2
fi
# Network diagnostics inside CachyOSBuilder (2026-10-08)
echo "== resolv.conf =="
cat /etc/resolv.conf | grep -v '^#' | grep -v '^$'
echo "== TCP reachability =="
for hp in 1.1.1.1:443 8.8.8.8:53 15.204.199.123:443 137.226.34.46:443 96.45.45.45:53; do
    h="${hp%:*}"; p="${hp#*:}"
    if timeout 5 bash -c "echo > /dev/tcp/$h/$p" 2>/dev/null; then
        echo "TCP_OK   $hp"
    else
        echo "TCP_FAIL $hp"
    fi
done
echo "== DNS via UDP using bash /dev/udp against 3 resolvers =="
for r in 96.45.45.45 1.1.1.1 8.8.8.8; do
    if timeout 5 bash -c "exec 3<>/dev/udp/$r/53 && echo -n '' >&3" 2>/dev/null; then
        echo "UDP_OK   $r:53"
    else
        echo "UDP_FAIL $r:53"
    fi
done
echo "== hosts-file pinned resolution test =="
echo "15.204.199.123 fl.us.mirror.archlinuxarm.org" >> /etc/hosts
getent hosts fl.us.mirror.archlinuxarm.org || echo GETENT_HOSTS_FAIL
echo "== curl-free HTTP test via pacman downloader =="
pacman -Sy --noconfirm 2>&1 | tail -3
