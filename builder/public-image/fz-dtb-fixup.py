#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""FroodzOS device-tree fix-up for Snapdragon X (Hamoa/Purwa) boards. Works on the compiled .dtb, so it applies to ANY board's
DTB without its source tree.

Rule "icc-orphan" (the one that makes the battery work): a Qualcomm PAS remoteproc node (ADSP by default) or a GENI serial engine
(`qcom,geni-i2c`, `-spi`, `-uart`, `-debug-uart`) that carries an
`interconnects` bandwidth vote through a NoC provider which is disabled (or missing) in the DTB can never probe: qcom_q6v5_pas
returns "failed to acquire interconnect path" forever, and battery, USB-C PD data, audio and the sensor hub all wait for it.
Deleting the vote (NULL path = "no vote") lets the driver probe. On boards where the firmware already booted the ADSP the
driver then simply attaches to the running processor; otherwise it loads firmware from /lib/firmware as usual.

Rule "orphan-usb3-phy": a DWC3 USB controller whose `phys` list names a PHY that is disabled in the DTB (a board that wires only the
USB 2.0 pair of a port, with the SuperSpeed PHY left disabled) never probes and keeps its suppliers' sync_state pending. The disabled
PHY entry is removed from `phys`/`phy-names` and `maximum-speed = "high-speed"` is set, so the port works as USB 2.0.

Rule "sound-nodp" (opt-in, `--sound-nodp`): a sound card node whose `*-dai-link` children use a DisplayPort controller (`qcom,*-dp`)
as their codec can never complete while the display subsystem is not probed (the images blacklist the display clock driver and run on
the firmware framebuffer): the whole card then defers forever with "DisplayPort0 Playback: codec dai not found" and no ALSA card appears even
though the audio processor, codecs and soundwire are up. The rule deletes those dai-link nodes so the speaker and headset links can bind.
Turn it off again once the display driver works.

    fz-dtb-fixup.py <in.dtb> <out.dtb> [--all-pas] [--sound-nodp] [--dry-run]

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
        m = re.match(r'^(?:[A-Za-z_][\w]*:\s*)*([\w,.+@/-]+)\s*\{$', line)
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
        if 'interconnects' not in props or 'disabled' in props.get('status', '"okay"'): continue
        if 'qcom,geni-' in comp: pass                      # I2C/SPI/UART serial engines: the same no-vote fallback the owner-tested I2C5/I2C9 fix uses
        elif '-pas' in comp and not (only_adsp and 'adsp' not in comp): pass
        else: continue
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


def strings(v):
    return re.findall(r'"([^"]*)"', v)


def plan_usb(nodes):
    by_ph = {cells(p['phandle'])[0]: path for path, p in nodes.items() if 'phandle' in p}
    out = []
    for path, props in nodes.items():
        if 'dwc3' not in props.get('compatible', '') or 'disabled' in props.get('status', '"okay"'): continue
        if 'phys' not in props or 'phy-names' not in props: continue
        names, vals, i, keep, drop = strings(props['phy-names']), cells(props['phys']), 0, [], []
        for nm in names:
            if i >= len(vals): break
            prov = by_ph.get(vals[i]); pp = nodes.get(prov, {}) if prov else {}
            n = cells(pp['#phy-cells'])[0] if '#phy-cells' in pp else 0
            ent = (nm, vals[i:i + 1 + n]); i += 1 + n
            (drop if prov is None or 'disabled' in pp.get('status', '"okay"') else keep).append(ent)
        if drop and keep:
            out.append((path, keep, drop, 'maximum-speed' not in props))
    return out


def plan_sound_nodp(nodes):
    """Paths of `*dai-link*` nodes whose `codec` child points at a DisplayPort controller node."""
    by_ph = {cells(p['phandle'])[0]: path for path, p in nodes.items() if 'phandle' in p}
    out = []
    for path, props in nodes.items():
        if 'dai-link' not in path.rsplit('/', 1)[-1]: continue
        cod = nodes.get(path + '/codec', {})
        vals = cells(cod['sound-dai']) if 'sound-dai' in cod else []
        tgt = nodes.get(by_ph.get(vals[0]), {}) if vals else {}
        if re.search(r'-dp"|displayport', tgt.get('compatible', '')):
            out.append(path)
    return sorted(out)


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if len(args) != 2: print(__doc__); return 2
    src, out = Path(args[0]), Path(args[1])
    nodes = parse(decompile(src))
    acts = plan(nodes, only_adsp='--all-pas' not in argv)
    usb = plan_usb(nodes)
    snd = plan_sound_nodp(nodes) if '--sound-nodp' in argv else []
    if not acts and not usb and not snd: print('fz-dtb-fixup: nothing to change'); shutil.copyfile(src, out); return 0
    if '--dry-run' in argv:
        for path, bad in acts: print('fz-dtb-fixup: would drop interconnect votes of %s (disabled providers: %s)' % (path, ', '.join(bad)))
        for path, keep, drop, _ in usb: print('fz-dtb-fixup: would drop PHY %s of %s (disabled provider), keep %s' % ([d[0] for d in drop], path, [k[0] for k in keep]))
        for path in snd: print('fz-dtb-fixup: would delete the DisplayPort dai-link %s' % path)
        return 0
    shutil.copyfile(src, out)
    for path, bad in acts:
        if subprocess.run(['fdtget', str(out), path, 'compatible'], capture_output=True).returncode != 0:
            print('fz-dtb-fixup: SKIPPED %s (path not found in the blob)' % path); continue
        for prop in ('interconnects', 'interconnect-names'):
            if prop in nodes[path]:
                subprocess.run(['fdtput', '-d', str(out), path, prop], check=True)
        print('fz-dtb-fixup: dropped interconnect votes of %s (disabled providers: %s)' % (path, ', '.join(bad)))
    for path, keep, drop, setspeed in usb:
        flat = [hex(c) for _, e in keep for c in e]
        subprocess.run(['fdtput', '-t', 'x', str(out), path, 'phys'] + flat, check=True)
        subprocess.run(['fdtput', '-t', 's', str(out), path, 'phy-names'] + [k[0] for k in keep], check=True)
        if setspeed: subprocess.run(['fdtput', '-t', 's', str(out), path, 'maximum-speed', 'high-speed'], check=True)
        print('fz-dtb-fixup: dropped PHY %s of %s (provider disabled); the port runs as USB 2.0' % ([d[0] for d in drop], path))
    for path in snd:
        subprocess.run(['fdtput', '-r', str(out), path], check=True)
        print('fz-dtb-fixup: deleted the DisplayPort dai-link %s (its codec, a DP controller, never probes without the display driver)' % path)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
