#!/usr/bin/env python3
"""Apply diagnostic 0017: usb-ddr path optional (mirrors 0016 for apps-usb).

Root cause (2026-10-17, native firmware checkpoints + static graph walk):
usb-ddr = usb_south_anoc -> ... -> qnm_snoc_sf -> [gem_noc] -> qns_llcc
-> llcc_mc -> ebi(mc_virt). gem_noc stays disabled (0.51s reset site), so
path_find can never complete: -EPROBE_DEFER at dwc3_qcom_interconnect_init,
after dwc3_core_probe already bound the xHCI child -> teardown.
Local-only diagnostic; NOT for publication or general ARM64 support.
"""
import sys
from pathlib import Path
SRC = Path('/home/builder/src/ksrc/drivers/usb/dwc3/dwc3-qcom.c')
s = SRC.read_text()

edits = [
('''static int dwc3_qcom_interconnect_enable(struct dwc3_qcom *qcom)
{
	int ret;

	ret = icc_enable(qcom->icc_path_ddr);
	if (ret)
		return ret;

	if (qcom->icc_path_apps) {
		ret = icc_enable(qcom->icc_path_apps);
		if (ret)
			icc_disable(qcom->icc_path_ddr);
	}

	return ret;
}''','''static int dwc3_qcom_interconnect_enable(struct dwc3_qcom *qcom)
{
	int ret = 0;

	if (qcom->icc_path_ddr) {
		ret = icc_enable(qcom->icc_path_ddr);
		if (ret)
			return ret;
	}

	if (qcom->icc_path_apps) {
		ret = icc_enable(qcom->icc_path_apps);
		if (ret && qcom->icc_path_ddr)
			icc_disable(qcom->icc_path_ddr);
	}

	return ret;
}'''),
('''static int dwc3_qcom_interconnect_disable(struct dwc3_qcom *qcom)
{
	int ret;

	ret = icc_disable(qcom->icc_path_ddr);
	if (ret)
		return ret;

	if (qcom->icc_path_apps) {
		ret = icc_disable(qcom->icc_path_apps);
		if (ret)
			icc_enable(qcom->icc_path_ddr);
	}

	return ret;
}''','''static int dwc3_qcom_interconnect_disable(struct dwc3_qcom *qcom)
{
	int ret = 0;

	if (qcom->icc_path_ddr) {
		ret = icc_disable(qcom->icc_path_ddr);
		if (ret)
			return ret;
	}

	if (qcom->icc_path_apps) {
		ret = icc_disable(qcom->icc_path_apps);
		if (ret && qcom->icc_path_ddr)
			icc_enable(qcom->icc_path_ddr);
	}

	return ret;
}'''),
('''	qcom->icc_path_ddr = of_icc_get(dev, "usb-ddr");
	if (IS_ERR(qcom->icc_path_ddr)) {
		return dev_err_probe(dev, PTR_ERR(qcom->icc_path_ddr),
				     "failed to get usb-ddr path\\n");
	}''','''	qcom->icc_path_ddr = of_icc_get(dev, "usb-ddr");
	if (IS_ERR(qcom->icc_path_ddr)) {
		/* DIAGNOSTIC 2026-10-17 (0017): usb-ddr optional for live
		 * boot. Route usb_south_anoc -> ... -> gem_noc -> mc_virt is
		 * severed (gem_noc stays off: 0.51s reset site), so path_find
		 * defers forever _after_ the xHCI child already bound,
		 * tearing USB down. Local-only, not for publication. */
		dev_warn(dev, "usb-ddr path unavailable (%ld), continuing without it\\n",
			 PTR_ERR(qcom->icc_path_ddr));
		qcom->icc_path_ddr = NULL;
	}'''),
('''	max_speed = usb_get_maximum_speed(qcom->dwc.dev);
	if (max_speed >= USB_SPEED_SUPER || max_speed == USB_SPEED_UNKNOWN) {
		ret = icc_set_bw(qcom->icc_path_ddr,
				USB_MEMORY_AVG_SS_BW, USB_MEMORY_PEAK_SS_BW);
	} else {
		ret = icc_set_bw(qcom->icc_path_ddr,
				USB_MEMORY_AVG_HS_BW, USB_MEMORY_PEAK_HS_BW);
	}
	if (ret) {
		dev_err(dev, "failed to set bandwidth for usb-ddr path: %d\\n", ret);
		goto put_path_apps;
	}''','''	max_speed = usb_get_maximum_speed(qcom->dwc.dev);
	if (qcom->icc_path_ddr) {
		if (max_speed >= USB_SPEED_SUPER || max_speed == USB_SPEED_UNKNOWN) {
			ret = icc_set_bw(qcom->icc_path_ddr,
					USB_MEMORY_AVG_SS_BW, USB_MEMORY_PEAK_SS_BW);
		} else {
			ret = icc_set_bw(qcom->icc_path_ddr,
					USB_MEMORY_AVG_HS_BW, USB_MEMORY_PEAK_HS_BW);
		}
		if (ret) {
			dev_err(dev, "failed to set bandwidth for usb-ddr path: %d\\n", ret);
			goto put_path_apps;
		}
	}'''),
('''put_path_ddr:
	icc_put(qcom->icc_path_ddr);
	return ret;''','''put_path_ddr:
	if (qcom->icc_path_ddr)
		icc_put(qcom->icc_path_ddr);
	return ret;'''),
('''static void dwc3_qcom_interconnect_exit(struct dwc3_qcom *qcom)
{
	icc_put(qcom->icc_path_ddr);
	if (qcom->icc_path_apps)
		icc_put(qcom->icc_path_apps);
}''','''static void dwc3_qcom_interconnect_exit(struct dwc3_qcom *qcom)
{
	if (qcom->icc_path_ddr)
		icc_put(qcom->icc_path_ddr);
	if (qcom->icc_path_apps)
		icc_put(qcom->icc_path_apps);
}'''),
]
for old, new in edits:
    n = s.count(old)
    assert n == 1, f'expected 1 match, found {n}: {old[:60]!r}'
    s = s.replace(old, new)
SRC.write_text(s)
print('APPLIED_0017: 6 sites, ddr optional, uninitialized-ret fixed (ret = 0)')
