# Synthetic boot-log fixtures

Every value in this directory is fabricated for the reader tests. No real
SSID, MAC address, serial number, PSK, username, e-mail address or hardware
identifier is present.

* `v2-legacy/` is the old root layout: `00-status.txt`, `01-kernel-kmsg.log`,
  `03-userspace-journal.log`, `summary.txt`, `history.tsv`, `events.log` and a
  snapshot. It has a fake oops, a fake Wi-Fi resume WARNING and failure, a
  failed unit, a fake prompt-injection line and fake secrets.
* `v3-recorder/` is the W4 section 15.3 layout: `boot.json`, a partial
  `index.json`, `summary.json`, `streams/<name>/NNNNNN.jsonl|log`, an
  `events/<stamp>-<reason>/` bundle and `05-writer.log`. It adds terminal
  records (command, exit code, duration), a fake typed secret and a fake power
  loss.

`tools/check-log-leaks.py` deliberately allows `tests/fixtures/logs/` for the
MAC/serial/PSK-shaped content checks so these fixtures can be tracked. The
path rules still apply everywhere else, and this folder is the only content
allowlist for synthetic secrets.
