#!/bin/bash
# HISTORICAL NETWORK REPRODUCER, NOT A CURRENT SETUP SCRIPT.
# Network constants are documentation-only redactions. Do not use as-is.
if [ "${FROODZOS_ALLOW_HISTORICAL_NETWORK:-0}" != 1 ]; then
    printf '%s\n' 'Refusing archived network changes; inspect and adapt in an isolated builder only' >&2
    exit 2
fi
# Phase 1 / Task 1.3b: fix DNS + mirrors in CachyOSBuilder (2026-10-08)
# Context: corporate FortiGate network; WSL inherited 192.0.2.10 + example.invalid
# which cannot resolve ALARM mirrors. systemd-resolved owns resolv.conf.
set -e

cat > /etc/pacman.d/mirrorlist <<'EOF'
# Arch Linux ARM mirrors, pinned 2026-10-08 (geo-redirect target had no tarball)
Server = https://fl.us.mirror.archlinuxarm.org/$arch/$repo
Server = https://de3.mirror.archlinuxarm.org/$arch/$repo
Server = http://mirror.archlinuxarm.org/$arch/$repo
EOF

mkdir -p /etc/systemd/resolved.conf.d
cat > /etc/systemd/resolved.conf.d/wsl-dns.conf <<'EOF'
[Resolve]
DNS=96.45.45.45 1.1.1.1
FallbackDNS=
Domains=~.
EOF

if systemctl restart systemd-resolved 2>/dev/null; then
    sleep 2
fi

if ! getent hosts fl.us.mirror.archlinuxarm.org >/dev/null 2>&1; then
    echo "resolved path failed; falling back to static resolv.conf"
    systemctl disable --now systemd-resolved 2>/dev/null || true
    rm -f /etc/resolv.conf
    printf "nameserver 96.45.45.45\nnameserver 1.1.1.1\n" > /etc/resolv.conf
fi

echo "== DNS test =="
getent hosts fl.us.mirror.archlinuxarm.org
echo "== pacman sync =="
pacman -Sy --noconfirm
echo SETUP_1_3B_OK
