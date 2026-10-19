#!/usr/bin/env python3
"""Check the kernel fork for newer qnoc/interconnect/Slim3 fixes past our pin."""
import json
import urllib.request
OWNER_REPO = 'jglathe/linux_ms_dev_kit'
BRANCH = 'jg/ubuntu-qcom-x1e-7.3rc'
PIN = '3f0d8691afa098ba378d7d5a3968f03219887719'


def get(url):
    req = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json',
                                               'User-Agent': 'kestrel-port'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


head = get(f'https://api.github.com/repos/{OWNER_REPO}/commits/{BRANCH}')
print('HEAD', head['sha'], head['commit']['committer']['date'], '| PIN', PIN,
      '| SAME' if head['sha'] == PIN else '| MOVED')
cmp = get(f'https://api.github.com/repos/{OWNER_REPO}/compare/{PIN}...{head["sha"]}')
print('AHEAD', cmp.get('ahead_by'), 'BEHIND', cmp.get('behind_by'), 'TOTAL', cmp.get('total_commits'))
hits = []
for c in cmp.get('commits', [])[:60]:
    msg = c['commit']['message'].splitlines()[0]
    if any(k in msg.lower() for k in ['qnoc', 'interconnect', 'icc', 'slim', '83n3', 'x1p', '42100',
                                      'dtb', 'dts', 'watchdog', 'reset', 'smmu', 'rpmh', 'pdh']):
        hits.append((c['sha'][:12], c['commit']['committer']['date'][:10], msg))
print('RELEVANT', len(hits))
for h in hits:
    print('  ', h[0], h[1], h[2][:130])
