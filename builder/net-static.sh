#!/bin/bash
# HISTORICAL NETWORK REPRODUCER, NOT A CURRENT SETUP SCRIPT.
# Network constants are documentation-only redactions. Do not use as-is.
if [ "${FROODZOS_ALLOW_HISTORICAL_NETWORK:-0}" != 1 ]; then
    printf '%s\n' 'Refusing archived network changes; inspect and adapt in an isolated builder only' >&2
    exit 2
fi
# Static eth0 via systemd-networkd + resolver policy in CachyOSBuilder (2026-10-08)
# Rationale: WSL's DHCP never hands out a lease on this corporate/VPN host and an
# unmanaged service keeps wiping manual config. Networkd becomes the owner.
set -e

systemctl disable --now systemd-resolved 2>/dev/null || true
systemctl mask systemd-resolved 2>/dev/null || true
rm -f /etc/resolv.conf
printf "nameserver 192.0.2.10\nnameserver 96.45.45.45\n" > /etc/resolv.conf

mkdir -p /etc/systemd/network
cat > /etc/systemd/network/20-eth0.network <<'EOF'
[Match]
Name=eth0

[Network]
DHCP=no
Address=192.0.2.12/20
Gateway=192.0.2.11
DNS=192.0.2.10
EOF

systemctl enable systemd-networkd 2>/dev/null || true
systemctl restart systemd-networkd
sleep 3

echo "== state =="
ip -4 addr show eth0 | grep inet || echo NO_ADDR
ip route || true
getent hosts fl.us.mirror.archlinuxarm.org || echo GETENT_FAIL
timeout 5 bash -c "echo > /dev/tcp/15.204.199.123/443" 2>/dev/null && echo TCP_OK_MIRROR || echo TCP_FAIL_MIRROR
echo "== pacman sync =="
pacman -Sy --noconfirm 2>&1 | tail -4
echo NETWORKD_STATIC_DONE
