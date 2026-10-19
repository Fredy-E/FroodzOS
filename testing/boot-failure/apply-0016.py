#!/usr/bin/env python3
"""Apply diagnostic dwc3 apps-usb-optional patch (0016) with assertions."""
P = '/home/builder/src/ksrc/drivers/usb/dwc3/dwc3-qcom.c'
src = open(P).read()

old_enable = """	ret = icc_enable(qcom->icc_path_apps);
	if (ret)
		icc_disable(qcom->icc_path_ddr);

	return ret;
}"""
new_enable = """	if (qcom->icc_path_apps) {
		ret = icc_enable(qcom->icc_path_apps);
		if (ret)
			icc_disable(qcom->icc_path_ddr);
	}

	return ret;
}"""
assert src.count(old_enable) == 1
src = src.replace(old_enable, new_enable)

old_disable = """	ret = icc_disable(qcom->icc_path_apps);
	if (ret)
		icc_enable(qcom->icc_path_ddr);

	return ret;
}"""
new_disable = """	if (qcom->icc_path_apps) {
		ret = icc_disable(qcom->icc_path_apps);
		if (ret)
			icc_enable(qcom->icc_path_ddr);
	}

	return ret;
}"""
assert src.count(old_disable) == 1
src = src.replace(old_disable, new_disable)

old_get = """	qcom->icc_path_apps = of_icc_get(dev, "apps-usb");
	if (IS_ERR(qcom->icc_path_apps)) {
		ret = dev_err_probe(dev, PTR_ERR(qcom->icc_path_apps),
				    "failed to get apps-usb path\\n");
		goto put_path_ddr;
	}"""
new_get = """	qcom->icc_path_apps = of_icc_get(dev, "apps-usb");
	if (IS_ERR(qcom->icc_path_apps)) {
		/* DIAGNOSTIC 2026-10-16 (0016): apps-usb optional for live
		 * boot (gem_noc stays off; its provider never registers).
		 * Local-only, not for publication. */
		dev_warn(dev, "apps-usb path unavailable (%ld), continuing without it\\n",
			 PTR_ERR(qcom->icc_path_apps));
		qcom->icc_path_apps = NULL;
	}"""
assert src.count(old_get) == 1
src = src.replace(old_get, new_get)

old_bw = """	ret = icc_set_bw(qcom->icc_path_apps, APPS_USB_AVG_BW, APPS_USB_PEAK_BW);
	if (ret) {
		dev_err(dev, "failed to set bandwidth for apps-usb path: %d\\n", ret);
		goto put_path_apps;
	}

	return 0;"""
new_bw = """	if (qcom->icc_path_apps) {
		ret = icc_set_bw(qcom->icc_path_apps, APPS_USB_AVG_BW, APPS_USB_PEAK_BW);
		if (ret) {
			dev_err(dev, "failed to set bandwidth for apps-usb path: %d\\n", ret);
			goto put_path_apps;
		}
	}

	return 0;"""
assert src.count(old_bw) == 1
src = src.replace(old_bw, new_bw)

old_put = """put_path_apps:
	icc_put(qcom->icc_path_apps);"""
new_put = """put_path_apps:
	if (qcom->icc_path_apps)
		icc_put(qcom->icc_path_apps);"""
assert src.count(old_put) == 1
src = src.replace(old_put, new_put)

old_exit = """static void dwc3_qcom_interconnect_exit(struct dwc3_qcom *qcom)
{
	icc_put(qcom->icc_path_ddr);
	icc_put(qcom->icc_path_apps);
}"""
new_exit = """static void dwc3_qcom_interconnect_exit(struct dwc3_qcom *qcom)
{
	icc_put(qcom->icc_path_ddr);
	if (qcom->icc_path_apps)
		icc_put(qcom->icc_path_apps);
}"""
assert src.count(old_exit) == 1
src = src.replace(old_exit, new_exit)

open(P, 'w').write(src)
print('APPLIED_0016')
