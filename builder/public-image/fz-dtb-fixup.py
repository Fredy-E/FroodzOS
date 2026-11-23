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

Rule "wsa-right-gpio13" (opt-in, `--wsa-right-gpio13`, Lenovo IdeaPad Slim 3 15Q8X10 / 83N3): the two WSA884x speaker amplifiers on the WSA SoundWire
bus share `reset-gpios = <&lpass_tlmm 12 ...>` in the upstream-derived board file, but on this board gpio12 only releases the LEFT amp; the
RIGHT amp (unique id 1, node `speaker@0,1`) has its own reset on lpass_tlmm gpio13 (proven on the laptop: driving gpio13 high made the
second amp enumerate and play). The rule rewrites the right amp's reset line to gpio13.

Rule "enable-nvme" (opt-in, `--enable-nvme`, Lenovo IdeaPad Slim 3 15Q8X10 / 83N3): the board file of the bring-up era leaves the PCIe controller of the internal
NVMe drive (`pcie@1bf8000`, "pcie6a") and its PHY (`phy@1bfc000`) disabled, so the internal disk and the Windows partition on it are invisible to Linux
(`lsblk` shows only the USB stick). The rule sets both to "okay"; the bandwidth votes of the controller through NoC providers that are disabled in the same
tree are then dropped by rule "icc-orphan" (which also covers `qcom,pcie-*` nodes). EXPERIMENTAL: the bring-up notes record a silent reset around the PCIe/NoC
probes of an older kernel, so use it only on a test boot entry.

Rule "nvme-gpio-dedupe" (opt-in, applied by `--enable-nvme`, same board, UNPROVEN on hardware): with the controller enabled, the PCI core
looks up `wake-gpios` (and `perst-gpios`) without a device, and a GPIO marked shared then oopses in `gpio_shared_add_proxy_lookup`
(kernel 7.3-rc3), which is the suspected cause of the lost Wi-Fi. On the shipped tree `wake-gpios` is repeated on the `pcie@0` root-port
child. The rule deletes `wake-gpios` and `perst-gpios` from the `pcie@1bf8000` controller node only when the same property name also exists
on one of its `pcie@*` child nodes, which keeps its copy; a property not duplicated on a child is never touched. This is a candidate fix: it
has NOT been proven on hardware.

    fz-dtb-fixup.py <in.dtb> <out.dtb> [--all-pas] [--sound-nodp] [--wsa-right-gpio13] [--enable-nvme] [--dry-run]
    --enable-nvme also applies rule "nvme-gpio-dedupe" (UNPROVEN on hardware).
    --nvme-dedupe-pins (with --enable-nvme) widens it to every controller `*-gpios` whose GPIO equals one on a root-port child under any name
    (here `perst-gpios` = the port's `reset-gpios`); also UNPROVEN.

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
        elif 'qcom,pcie-' in comp: pass                    # PCIe controllers (an enabled one can never probe through a disabled NoC)
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


def plan_wsa_right(nodes):
    """(path, [phandle, 13, flags]) for each right WSA884x amp (`speaker@0,1`, compatible sdw20217020400) whose reset is gpio12."""
    out = []
    for path, props in nodes.items():
        if not path.rsplit('/', 1)[-1].startswith('speaker@') or not path.endswith('@0,1'): continue
        if 'sdw20217020400' not in props.get('compatible', '') or 'reset-gpios' not in props: continue
        v = cells(props['reset-gpios'])
        if len(v) == 3 and v[1] == 12: out.append((path, [v[0], 13, v[2]]))
    return sorted(out)


def plan_enable_nvme(nodes):
    """Paths of the disabled PCIe controller (`pcie@1bf8000`, qcom,pcie-*) and PHY (`phy@1bfc000`) of the internal NVMe slot."""
    out = []
    for path, props in nodes.items():
        last = path.rsplit('/', 1)[-1]
        if last == 'pcie@1bf8000' and 'qcom,pcie-' in props.get('compatible', '') and 'disabled' in props.get('status', ''): out.append(path)
        if last == 'phy@1bfc000' and 'pcie-phy' in props.get('compatible', '') and 'disabled' in props.get('status', ''): out.append(path)
    return sorted(out)


def nvme_gpio_child(nodes, path, prop, by_pin=False):
    """The `pcie@*` child of `path` that repeats `prop` (same name, or with by_pin the same GPIO cells under any `*-gpios` name), or None."""
    for p in sorted(nodes):
        if p.rsplit('/', 1)[0] != path or not p.rsplit('/', 1)[-1].startswith('pcie@'): continue
        if prop in nodes[p]: return p
        if by_pin and any(k.endswith('-gpios') and v == nodes[path][prop] for k, v in nodes[p].items()): return p
    return None


def plan_nvme_gpio_dedupe(nodes, by_pin=False):
    """(controller path, [props]) for gpios of the NVMe controller that are duplicated on one of its `pcie@*` children (the child keeps them).
    Default: `perst-gpios` / `wake-gpios` repeated under the same name. by_pin (`--nvme-dedupe-pins`): any `*-gpios` property of the controller whose
    GPIO cells equal a gpio property of a child under any name (the shipped tree has `perst-gpios` on the controller and `reset-gpios` on the port)."""
    out = []
    for path, props in nodes.items():
        if path.rsplit('/', 1)[-1] != 'pcie@1bf8000' or 'qcom,pcie-' not in props.get('compatible', ''): continue
        names = [k for k in props if k.endswith('-gpios')] if by_pin else ['perst-gpios', 'wake-gpios']
        dup = sorted(k for k in names if k in props and nvme_gpio_child(nodes, path, k, by_pin))
        if dup: out.append((path, dup))
    return sorted(out)


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if len(args) != 2: print(__doc__); return 2
    src, out = Path(args[0]), Path(args[1])
    nodes = parse(decompile(src))
    nvme = plan_enable_nvme(nodes) if '--enable-nvme' in argv else []
    dedupe = plan_nvme_gpio_dedupe(nodes, by_pin='--nvme-dedupe-pins' in argv) if '--enable-nvme' in argv else []
    for path in nvme: nodes[path]['status'] = '"okay"'      # so the vote rule below sees the controller as enabled
    acts = plan(nodes, only_adsp='--all-pas' not in argv)
    usb = plan_usb(nodes)
    snd = plan_sound_nodp(nodes) if '--sound-nodp' in argv else []
    wsa = plan_wsa_right(nodes) if '--wsa-right-gpio13' in argv else []
    if not acts and not usb and not snd and not wsa and not nvme and not dedupe: print('fz-dtb-fixup: nothing to change'); shutil.copyfile(src, out); return 0
    if '--dry-run' in argv:
        for path in nvme: print('fz-dtb-fixup: would enable %s (internal NVMe PCIe controller/PHY)' % path)
        for path, props in dedupe:
            for prop in props: print('fz-dtb-fixup: would delete %s of %s (duplicated on its root port child)' % (prop, path))
        for path, bad in acts: print('fz-dtb-fixup: would drop interconnect votes of %s (disabled providers: %s)' % (path, ', '.join(bad)))
        for path, keep, drop, _ in usb: print('fz-dtb-fixup: would drop PHY %s of %s (disabled provider), keep %s' % ([d[0] for d in drop], path, [k[0] for k in keep]))
        for path in snd: print('fz-dtb-fixup: would delete the DisplayPort dai-link %s' % path)
        for path, _ in wsa: print('fz-dtb-fixup: would move the reset of the right speaker amp %s to lpass_tlmm gpio13' % path)
        return 0
    shutil.copyfile(src, out)
    for path in nvme:
        subprocess.run(['fdtput', '-t', 's', str(out), path, 'status', 'okay'], check=True)
        print('fz-dtb-fixup: enabled %s (internal NVMe PCIe controller/PHY)' % path)
    for path, props in dedupe:
        for prop in props:
            child = nvme_gpio_child(nodes, path, prop, '--nvme-dedupe-pins' in argv)
            subprocess.run(['fdtput', '-d', str(out), path, prop], check=True)
            print('fz-dtb-fixup: deleted %s of %s (duplicated on its root port child %s)' % (prop, path, child))
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
    for path, val in wsa:
        subprocess.run(['fdtput', '-t', 'x', str(out), path, 'reset-gpios'] + [hex(c) for c in val], check=True)
        print('fz-dtb-fixup: right speaker amp %s now resets on lpass_tlmm gpio13' % path)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
