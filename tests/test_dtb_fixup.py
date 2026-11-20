#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""fz-dtb-fixup: drops the interconnect votes of an ADSP whose NoC provider is disabled, and leaves a healthy one alone."""
import importlib.util, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fzfix', ROOT / 'builder/public-image/fz-dtb-fixup.py')
fz = importlib.util.module_from_spec(spec); spec.loader.exec_module(fz)

DTS = """/dts-v1/;
/ { #address-cells = <2>; #size-cells = <2>;
  soc@0 { #address-cells = <2>; #size-cells = <2>;
    noc_bad: interconnect@1 { #interconnect-cells = <2>; status = "disabled"; phandle = <0x10>; };
    noc_ok: interconnect@2 { #interconnect-cells = <2>; phandle = <0x11>; };
    remoteproc@10 { compatible = "qcom,x1e80100-adsp-pas"; interconnects = <0x10 0 7 0x37 1 7>; interconnect-names = "x"; };
    remoteproc@20 { compatible = "qcom,x1e80100-cdsp-pas"; interconnects = <0x11 0 7 0x37 1 7>; };
    phy_hs: phy@40 { #phy-cells = <0>; phandle = <0x20>; };
    phy_ss: phy@50 { #phy-cells = <1>; status = "disabled"; phandle = <0x21>; };
    usb@60 { compatible = "qcom,x1e80100-dwc3", "qcom,snps-dwc3"; phys = <0x20 0x21 0>; phy-names = "usb2-phy", "usb3-phy"; status = "okay"; };
    i2c@30 { compatible = "qcom,geni-i2c"; interconnects = <0x11 0 7 0x10 1 7>; interconnect-names = "qup-core", "qup-config"; status = "okay"; };
    spi@30 { compatible = "qcom,geni-spi"; interconnects = <0x10 1 7>; status = "disabled"; };
    pcie@1bf8000 { compatible = "qcom,pcie-x1e80100"; status = "disabled"; interconnects = <0x10 3 7 0x11 1 7>; interconnect-names = "pcie-mem", "cpu-pcie"; };
    phy@1bfc000 { compatible = "qcom,x1p42100-qmp-gen4x4-pcie-phy"; status = "disabled"; };
    dp0: displayport-controller@70 { compatible = "qcom,x1e80100-dp"; phandle = <0x30>; };
    wcd: codec@80 { compatible = "qcom,wcd9385-codec"; phandle = <0x31>; };
    soundwire@90 { #address-cells = <2>; #size-cells = <0>;
      speaker@0,0 { compatible = "sdw20217020400"; reg = <0 0>; reset-gpios = <0x41 12 1>; };
      speaker@0,1 { compatible = "sdw20217020400"; reg = <0 1>; reset-gpios = <0x41 12 1>; };
    };
  };
  sound {
    compatible = "qcom,x1e80100-sndcard";
    displayport-0-dai-link { link-name = "DisplayPort0 Playback"; cpu { sound-dai = <0x32 0>; }; codec { sound-dai = <0x30 0>; }; };
    wcd-playback-dai-link { link-name = "WCD Playback"; cpu { sound-dai = <0x32 1>; }; codec { sound-dai = <0x31 0>; }; };
  };
};
"""


@unittest.skipUnless(shutil.which('dtc') and shutil.which('fdtput'), 'dtc/fdtput not installed')
class Fixup(unittest.TestCase):
    def run_fix(self, *extra):
        d = Path(tempfile.mkdtemp()); (d / 'a.dts').write_text(DTS)
        subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', '-o', str(d / 'a.dtb'), str(d / 'a.dts')], check=True, capture_output=True)
        self.assertEqual(fz.main([str(d / 'a.dtb'), str(d / 'b.dtb'), *extra]), 0)
        return subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', str(d / 'b.dtb')], capture_output=True, text=True).stdout

    def test_adsp_with_disabled_provider_loses_the_vote(self):
        out = self.run_fix()
        self.assertNotIn('interconnect-names = "x"', out)        # the adsp's names are gone (the disabled pcie node keeps its own)
        self.assertEqual(out.count('interconnects ='), 3)       # the cdsp (healthy provider), the disabled spi and the disabled pcie keep theirs
        self.assertNotIn('qup-config', out)                      # the i2c engine routed through the disabled provider lost its votes

    def test_usb_controller_with_disabled_ss_phy_becomes_usb2(self):
        out = self.run_fix()
        self.assertIn('maximum-speed = "high-speed"', out)
        self.assertIn('phy-names = "usb2-phy";', out)
        self.assertNotIn('usb3-phy', out)

    def test_sound_nodp_is_opt_in_and_removes_only_the_displayport_link(self):
        self.assertIn('displayport-0-dai-link', self.run_fix())
        out = self.run_fix('--sound-nodp')
        self.assertNotIn('displayport-0-dai-link', out)
        self.assertIn('wcd-playback-dai-link', out)

    def test_wsa_right_gpio13_is_opt_in_and_moves_only_the_right_amp(self):
        self.assertEqual(self.run_fix().count('reset-gpios = <0x41 0x0c 0x01>'), 2)
        out = self.run_fix('--wsa-right-gpio13')
        self.assertEqual(out.count('reset-gpios = <0x41 0x0c 0x01>'), 1)     # the left amp stays on gpio12
        self.assertEqual(out.count('reset-gpios = <0x41 0x0d 0x01>'), 1)     # the right amp (speaker@0,1) moved to gpio13

    def test_enable_nvme_is_opt_in_and_drops_the_orphaned_pcie_votes(self):
        base = self.run_fix()
        self.assertEqual(base.count('status = "disabled"'), 5)     # noc_bad, spi, phy_ss, pcie and its phy
        out = self.run_fix('--enable-nvme')
        self.assertEqual(out.count('status = "disabled"'), 3)      # the controller and its phy are now enabled
        self.assertIn('pcie-phy', out)
        self.assertEqual(out.count('interconnects ='), 2)          # the pcie controller lost its votes (provider is disabled); cdsp and spi keep theirs
        self.assertNotIn('pcie-mem', out)

    def test_dry_run_changes_nothing(self):
        d = Path(tempfile.mkdtemp()); (d / 'a.dts').write_text(DTS)
        subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', '-o', str(d / 'a.dtb'), str(d / 'a.dts')], check=True, capture_output=True)
        self.assertEqual(fz.main([str(d / 'a.dtb'), str(d / 'b.dtb'), '--dry-run']), 0)
        self.assertFalse((d / 'b.dtb').exists())

    def test_plan_ignores_healthy_provider(self):
        nodes = fz.parse(DTS.replace('0x10 0 7', '0x11 0 7'))
        self.assertEqual(fz.plan(nodes), [])


if __name__ == '__main__':
    unittest.main()
