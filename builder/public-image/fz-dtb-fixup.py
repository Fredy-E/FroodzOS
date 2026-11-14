#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""FroodzOS device-tree fix-up for Snapdragon X (Hamoa/Purwa) boards. Works on the compiled .dtb, so it applies to ANY board's
DTB without its source tree.

Rule "icc-orphan" (the one that makes the battery work): a Qualcomm PAS remoteproc node (ADSP by default) that carries an
`interconnects` bandwidth vote through a NoC provider which is disabled (or missing) in the DTB can never probe: qcom_q6v5_pas
returns "failed to acquire interconnect path" forever, and battery, USB-C PD data, audio and the sensor hub all wait for it.
Deleting the vote (NULL path = "no vote") lets the driver probe. On boards where the firmware already booted the ADSP the
driver then simply attaches to the running processor; otherwise it loads firmware from /lib/firmware as usual.

    fz-dtb-fixup.py <in.dtb> <out.dtb> [--all-pas] [--dry-run]

Needs dtc, fdtput (package dtc). The input is never modified. Prints one line per action; exit 0 even when nothing is needed.
"""
import re, shutil, subprocess, sys
from pathlib import Path


def decompile(dtb):
    return subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', str(dtb)], check=True, capture_output=True, text=True).stdout


def parse(dts):
    """Return nodes: path -> {props: {name: raw-string}} (properties are kept as raw text; only what the rule needs is decoded)."""
    nodes, stack, pend = {}, [], ''
    for raw in dts.splitlines():
        line = (pend + ' ' + raw.strip()).strip(); pend = ''
        if '=' in line and not line.endswith(';') and not line.endswith('{'):
            pend = line; continue            # property continued on the next line
        m = re.match(r'^(?:[A-Za-z_][\w]*:\s*)?([\w,.+@/-]+)\s*\{$', line)
        if m:
            name = m.group(1)
            path = '/' if not stack else (('' if stack[-1] == '/' else stack[-1]) + '/' + name)
            if not stack and name == '/': path = '/'
            stack.append(path); nodes.setdefault(path, {}); continue
        if line == '};':
            if stack: stack.pop()
            continue
        if stack and line.endswith(';') and not line.startswith('/'):
            k, _, v = line[:-1].partition('=')
            nodes[stack[-1]][k.strip()] = v.strip()
    return nodes


def cells(v):
    return [int(x, 0) for x in re.findall(r'0x[0-9a-fA-F]+|\b\d+\b', v)]


def plan(nodes, only_adsp=True):
    by_ph = {}
    for p, props in nodes.items():
        if 'phandle' in props:
            by_ph[cells(props['phandle'])[0]] = p
    actions = []
    for path, props in nodes.items():
        comp = props.get('compatible', '')
        if '-pas' not in comp or 'interconnects' not in props: continue
        if only_adsp and 'adsp' not in comp: continue
        vals, i, bad = cells(props['interconnects']), 0, []
        while i < len(vals):
            prov = by_ph.get(vals[i])
            pp = nodes.get(prov, {}) if prov else {}
            n = cells(pp['#interconnect-cells'])[0] if '#interconnect-cells' in pp else 2
            if prov is None or 'disabled' in pp.get('status', '"okay"'):
                bad.append(prov or 'phandle 0x%x' % vals[i])
            i += 1 + n
        if bad:
            actions.append((path, sorted(set(bad))))
    return actions


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if len(args) != 2: print(__doc__); return 2
    src, out = Path(args[0]), Path(args[1])
    nodes = parse(decompile(src))
    acts = plan(nodes, only_adsp='--all-pas' not in argv)
    if not acts: print('fz-dtb-fixup: nothing to change'); shutil.copyfile(src, out); return 0
    if '--dry-run' in argv:
        for path, bad in acts: print('fz-dtb-fixup: would drop interconnect votes of %s (disabled providers: %s)' % (path, ', '.join(bad)))
        return 0
    shutil.copyfile(src, out)
    for path, bad in acts:
        for prop in ('interconnects', 'interconnect-names'):
            if prop in nodes[path]:
                subprocess.run(['fdtput', '-d', str(out), path, prop], check=True)
        print('fz-dtb-fixup: dropped interconnect votes of %s (disabled providers: %s)' % (path, ', '.join(bad)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
