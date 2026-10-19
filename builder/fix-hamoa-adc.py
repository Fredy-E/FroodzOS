#!/usr/bin/env python3
"""Fix duplicate adc@9000 under pmk8550 in hamoa-pmics.dtsi (2026-10-08).

Two nodes named adc@9000 exist under pmic@0: pmk8550_adc_tm (a stale partial
copy with one channel and old-style interrupts) and pmk8550_vadc (the complete
node with interrupts-extended + full channel set). Merge them into ONE node
with both labels, keeping the vadc node's structure and adding adc_tm's
#thermal-sensor-cells and its channel@18e (VPH_PWR) child.
"""
import re
import sys

PATH = "/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/hamoa-pmics.dtsi"
src = open(PATH, encoding="utf-8").read()
orig = src


def extract_block(text, header_re):
    """Return (start, end, block_text) for the node opened by header_re,
    matching braces from the opening '{'."""
    m = re.search(header_re, text)
    if not m:
        sys.exit("header not found: " + header_re.pattern)
    start = m.start()
    open_brace = text.index("{", m.start())
    depth = 0
    for i in range(open_brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = text.index("\n", i) + 1
                return start, end, text[start:end]
    sys.exit("unbalanced braces")


# 1) extract the stale pmk8550_adc_tm node and its channel@18e child
s1, e1, tm_block = extract_block(src, r"\t\tpmk8550_adc_tm: adc@9000 \{")
cm = re.search(r"\n(\t\t\tchannel@18e \{.*?\n\t\t\t\};)\n", tm_block, re.S)
if not cm:
    sys.exit("channel@18e not found inside pmk8550_adc_tm")
channel_18e = cm.group(1)

# 2) remove the stale node entirely
src = src[:s1] + src[e1:]

# 3) merge into the surviving vadc node
s2, e2, vadc_block = extract_block(src, r"\t\tpmk8550_vadc: adc@9000 \{")
new_block = vadc_block.replace(
    "\t\tpmk8550_vadc: adc@9000 {",
    "\t\tpmk8550_adc_tm: pmk8550_vadc: adc@9000 {",
    1,
)
if "#thermal-sensor-cells" not in new_block:
    new_block = new_block.replace(
        "\t\t\t#io-channel-cells = <1>;\n",
        "\t\t\t#io-channel-cells = <1>;\n\t\t\t#thermal-sensor-cells = <1>;\n",
        1,
    )
# append the channel just before the node's closing "\t\t};"
idx = new_block.rfind("\n\t\t};")
new_block = new_block[:idx] + "\n\n" + channel_18e + new_block[idx:]
src = src[:s2] + new_block + src[e2:]

if src.count("adc@9000 {") != 1:
    sys.exit("merge failed: expected exactly one adc@9000 node")
if src != orig:
    open(PATH, "w", encoding="utf-8").write(src)
print("MERGED: one adc@9000 node, labels pmk8550_adc_tm + pmk8550_vadc, channel@18e preserved")
