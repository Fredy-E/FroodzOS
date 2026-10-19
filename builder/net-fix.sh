#!/bin/bash
# HISTORICAL NETWORK REPRODUCER, NOT A CURRENT SETUP SCRIPT.
# Network constants are documentation-only redactions. Do not use as-is.
if [ "${FROODZOS_ALLOW_HISTORICAL_NETWORK:-0}" != 1 ]; then
    printf '%s\n' 'Refusing archived network changes; inspect and adapt in an isolated builder only' >&2
    exit 2
fi
# DNS + hosts persistence fix in CachyOSBuilder (2026-10-08)
# WSL NAT is healthy; DHCP on eth0 and DNS are not. Windows-side DNS works.
set -e

if ! grep -q "generateHosts=false" /etc/wsl.conf; then
    printf "generateHosts=false\n" >> /etc/wsl.conf
fi

if ! grep -q "fl.us.mirror.archlinuxarm.org" /etc/hosts; then
    cat >> /etc/hosts <<'EOF'
15.204.199.123 fl.us.mirror.archlinuxarm.org
137.226.34.46 de3.mirror.archlinuxarm.org
EOF
fi

DNS_FOUND=""
for r in 192.0.2.10 96.45.45.45 8.8.8.8 1.1.1.1; do
    printf "nameserver %s\n" "$r" > /etc/resolv.conf
    if getent hosts github.com >/dev/null 2>&1; then
        DNS_FOUND="$r"
        break
    fi
done
if [ -n "$DNS_FOUND" ]; then
    echo "DNS_WORKS via $DNS_FOUND"
else
    echo "ALL_DNS_FAILED (hosts pins still usable for pacman)"
    printf "nameserver 96.45.45.45\n" > /etc/resolv.conf
fi

echo "== resolver check =="
getent hosts fl.us.mirror.archlinuxarm.org
echo "== pacman sync =="
pacman -Sy --noconfirm 2>&1 | tail -4
echo NET_FIX_DONE
