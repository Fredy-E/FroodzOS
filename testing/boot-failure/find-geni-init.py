#!/usr/bin/env python3
"""Exact initcall names for the GENI family (System.map-verified)."""
import re
hits = {}
for line in open('/home/builder/src/ksrc/System.map', errors='replace'):
    parts = line.split()
    if len(parts) == 3 and re.search(r'geni|gsi', parts[2]):
        hits.setdefault(parts[2], parts[0])
for n in sorted(hits):
    print(n, hits[n])
