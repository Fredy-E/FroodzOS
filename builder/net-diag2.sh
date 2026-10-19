#!/bin/bash
# HISTORICAL NETWORK REPRODUCER, NOT A CURRENT SETUP SCRIPT.
# Network constants are documentation-only redactions. Do not use as-is.
if [ "${FROODZOS_ALLOW_HISTORICAL_NETWORK:-0}" != 1 ]; then
    printf '%s\n' 'Refusing archived network changes; inspect and adapt in an isolated builder only' >&2
    exit 2
fi
# Net diag round 2: VM -> host reachability (2026-10-08)
echo "== interfaces/routes =="
ip -4 addr show | grep -E 'inet |^[0-9]'
ip route
echo "== host-side targets =="
for hp in 192.0.2.10:53 192.0.2.10:443 192.0.2.10:80; do
    h="${hp%:*}"; p="${hp#*:}"
    timeout 5 bash -c "echo > /dev/tcp/$h/$p" 2>/dev/null && echo "TCP_OK   $hp" || echo "TCP_FAIL $hp"
done
GW=$(ip route | awk '/default/ {print $3}')
echo "gateway=$GW"
if [ -n "$GW" ]; then
    timeout 5 bash -c "echo > /dev/tcp/$GW/443" 2>/dev/null && echo "TCP_OK   gw:443" || echo "TCP_FAIL gw:443"
    timeout 5 bash -c "echo > /dev/tcp/$GW/53" 2>/dev/null && echo "TCP_OK   gw:53" || echo "TCP_FAIL gw:53"
fi
