#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Streaming, line-oriented redactor for FroodzOS boot and session logs.

Python 3 standard library only. The redactor is the reader-side counterpart of
the capture-time filter: run it over a log copy before it is pasted into a chat,
attached to an issue or scanned by another tool.

Rules:
* High-entropy secrets are replaced completely.
* Low-entropy identifiers (SSID, MAC, serial, e-mail, user, hostname) become a
  stable keyed pseudonym ``<redacted:kind:12hex>`` so correlation across boots
  still works.
* The pseudonym key (32 random bytes, hex) must not live in the repository. A
  throwaway key is fine for a one-off read; without the key the values cannot be
  compared with tokens from another run.
* Debugging facts are kept: kernel pointers, PCI/USB IDs, firmware versions,
  error codes, unit names, PIDs, priorities.
* Already-redacted tokens are never hashed twice (idempotent).

CLI:
    fz_redact.py --key-file KEY --in FILE [--out FILE] [--stats]
    fz_redact.py --key HEX   < input > output

Never pass a real secret on the command line; it lands in the shell history.
"""
import argparse
import hashlib
import hmac
import ipaddress
import os
import re
import sys

MAX_LINE = 64 * 1024
MAX_KEY_BLOCK = 64 * 1024
TOKEN_HEX = 12
MARK = "<redacted:"

SAFE_USERS = {
    "root", "live", "nobody", "daemon", "bin", "sys", "sync", "games", "man",
    "lp", "mail", "news", "uucp", "proxy", "www-data", "backup", "list",
    "irc", "gnats", "messagebus", "systemd-network", "systemd-resolve",
    "systemd-timesync", "polkitd", "rtkit", "colord", "sddm", "pipewire",
    "wireplumber", "avahi", "nm-openvpn", "chrony", "dhcpcd",
}
SAFE_HOSTS = {"localhost", "localhost.localdomain", "live", "froodzos", "(none)"}

RE_ALREADY = re.compile(re.escape(MARK))
RE_URL_USERINFO = re.compile(
    r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*://)(?P<userinfo>[^/\s:@]+(?::[^/\s@]*)?)@")
RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")
RE_MAC = re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b|\b[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}\b")
RE_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
RE_GITHUB = re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b")
RE_AWS = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
RE_SK = re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}\b")
RE_SLACK = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")
RE_GOOGLE = re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")
RE_GITLAB = re.compile(r"\bglpat-[A-Za-z0-9_-]{16,}\b")
RE_NPM = re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b")
RE_HF = re.compile(r"\bhf_[A-Za-z0-9]{20,}\b")
RE_STRIPE = re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b")
RE_PRIVKEY_BEGIN = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")
RE_PRIVKEY_END = re.compile(r"-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")
RE_AUTH = re.compile(r"(?i)(?P<head>(?:proxy-)?authorization)\s*:\s*(?P<scheme>[A-Za-z]+)?\s*(?P<cred>[^\s,;]+)")
RE_COOKIE = re.compile(r"(?i)(?P<head>(?:set-)?cookie)\s*:\s*(?P<val>[^\r\n]+)")
RE_BEARER = re.compile(r"(?i)\b(?P<scheme>bearer|basic|token)\s+(?P<cred>[A-Za-z0-9._~+/=-]{8,})")
RE_WPA = re.compile(
    r"(?i)\b(?P<key>psk|passphrase|password|wep-key[0-3]?|private_key_passwd|"
    r"wifi-sec\.psk|802-11-wireless-security\.psk)\s*(?P<sep>[=:])\s*(?P<q>[\"']?)(?P<val>[^\"'\r\n]*)(?P=q)")
RE_SSID = re.compile(r"(?i)\b(?P<key>ssid)\s*(?P<sep>[=:])\s*(?P<q>[\"']?)(?P<val>[^\"'\r\n]*)(?P=q)")
RE_SERIAL = re.compile(
    r"(?i)\b(?P<key>serial(?:\s*number)?|serialno|s/n|iserialnumber)\s*(?P<sep>[=:])\s*"
    r"(?P<q>[\"']?)(?P<val>[^\"'\s]+)(?P=q)")
RE_SERIAL_USB = re.compile(r"(?i)\b(?P<key>iserial)\s+\d+\s+(?P<val>\S+)")
RE_HOST = re.compile(r"(?i)\b(?P<key>hostname|host\s+name)\s*(?P<sep>[=:])\s*(?P<q>[\"']?)(?P<val>[^\"'\s]+)(?P=q)")
RE_USER_UID = re.compile(r"\buid=\d+\((?P<val>[^)]+)\)")
RE_USER_HOME = re.compile(r"(?P<pre>/home/)(?P<val>[^/\s:]+)")
RE_USER_WIN = re.compile(r"(?i)(?P<pre>[A-Za-z]:\\Users\\)(?P<val>[^\\\s]+)")
RE_USER_KV = re.compile(r"(?i)\b(?P<key>user|username|login)\s*=\s*(?P<q>[\"']?)(?P<val>[^\"'\s,]+)(?P=q)")
RE_SUDO_PROMPT = re.compile(r"(?i)^(?:\[sudo\]\s*)?password for (?P<user>[^:]+):\s*$")
RE_PASS_PROMPT = re.compile(r"(?i)^(?P<prompt>password|passphrase|pin|token)\s*:\s*$")
RE_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
RE_IPV6 = re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{0,4}\b")

TOKEN_PATTERNS = (
    ("github", RE_GITHUB),
    ("aws", RE_AWS),
    ("api-key", RE_SK),
    ("slack", RE_SLACK),
    ("google", RE_GOOGLE),
    ("gitlab", RE_GITLAB),
    ("npm", RE_NPM),
    ("huggingface", RE_HF),
    ("stripe", RE_STRIPE),
    ("jwt", RE_JWT),
)


class Redactor:
    def __init__(self, key, redact_private_ips=False):
        if len(key) < 16:
            raise ValueError("key must be at least 16 bytes")
        self.key = key
        self.redact_private_ips = redact_private_ips
        self.stats = {}
        self._await_secret = False

    def token(self, kind, value):
        digest = hmac.new(self.key, value.strip().encode("utf-8", "surrogateescape"),
                          hashlib.sha256).hexdigest()[:TOKEN_HEX]
        self.stats[kind] = self.stats.get(kind, 0) + 1
        return "%s%s:%s>" % (MARK, kind, digest)

    def _already(self, value):
        return MARK in value

    def _safe_user(self, value):
        return value.lower() in SAFE_USERS

    def _safe_host(self, value):
        return value.lower() in SAFE_HOSTS

    def line(self, raw):
        try:
            return self._line(raw)
        except Exception:
            self.stats["redaction-error"] = self.stats.get("redaction-error", 0) + 1
            return "%sredaction-error>\n" % MARK

    def _line(self, raw):
        newline = ""
        line = raw
        if line.endswith("\n"):
            line, newline = line[:-1], "\n"
        if len(line) > MAX_LINE:
            line = line[:MAX_LINE] + " <truncated-line>"

        prompt = RE_SUDO_PROMPT.match(line)
        if prompt:
            user = prompt.group("user")
            if not self._safe_user(user):
                line = line[:prompt.start("user")] + self.token("user", user) + line[prompt.end("user"):]
            self._await_secret = True
            return line + newline
        if RE_PASS_PROMPT.match(line) and not self._already(line):
            self._await_secret = True
            return line + newline
        if self._await_secret:
            self._await_secret = False
            if line.strip() and not line.lstrip().startswith(("#", "$", ">")):
                return self.token("typed-secret", line) + newline

        m = RE_AUTH.search(line)
        if m and not self._already(m.group("cred")):
            scheme = (m.group("scheme") or "").strip()
            cred = m.group("cred").strip()
            kind = "auth-" + scheme.lower() if scheme else "auth"
            start = m.start("scheme") if scheme else m.start("cred")
            value = (scheme + " " + self.token(kind, cred)) if scheme else self.token(kind, cred)
            line = line[:start] + value + line[m.end("cred"):]
        m = RE_COOKIE.search(line)
        if m and not self._already(m.group("val")):
            value = self._redact_cookie(m.group("val"))
            line = line[:m.start("val")] + value + line[m.end("val"):]

        line = RE_URL_USERINFO.sub(
            lambda x: x.group("scheme") + self.token("url-credential", x.group("userinfo")) + "@", line)
        line = RE_BEARER.sub(
            lambda x: x.group("scheme") + " " + self.token("bearer", x.group("cred")), line)
        for kind, rx in TOKEN_PATTERNS:
            line = rx.sub(lambda x, k=kind: self.token(k, x.group(0)), line)

        line = self._redact_key_values(line)
        line = RE_EMAIL.sub(lambda x: self.token("email", x.group(0)), line)
        line = RE_MAC.sub(lambda x: self.token("mac", x.group(0)), line)
        line = RE_USER_UID.sub(
            lambda x: "uid=" + re.search(r"\d+", x.group(0)).group(0) + "(" +
            (x.group("val") if self._safe_user(x.group("val")) else self.token("user", x.group("val"))) + ")",
            line)
        line = RE_USER_HOME.sub(
            lambda x: x.group("pre") + (x.group("val") if self._safe_user(x.group("val"))
                                        else self.token("user", x.group("val"))), line)
        line = RE_USER_WIN.sub(
            lambda x: x.group("pre") + (x.group("val") if self._safe_user(x.group("val"))
                                        else self.token("user", x.group("val"))), line)
        line = RE_USER_KV.sub(
            lambda x: x.group("key") + "=" + (x.group("val") if self._safe_user(x.group("val"))
                                              else self.token("user", x.group("val"))), line)
        line = self._redact_ips(line)
        return line + newline

    def _redact_key_values(self, line):
        for rx in (RE_WPA, RE_SSID, RE_SERIAL, RE_SERIAL_USB, RE_HOST):
            def repl(m, r=rx):
                value = m.group("val")
                if not value or self._already(value):
                    return m.group(0)
                key = m.group("key")
                if key.lower() == "ssid":
                    kind = "ssid"
                elif key.lower() in ("hostname", "host name"):
                    if self._safe_host(value):
                        return m.group(0)
                    kind = "host"
                elif key.lower() == "iserial":
                    kind = "serial"
                elif key.lower().startswith(("psk", "passphrase", "password", "wep-key",
                                             "private_key_passwd", "wifi-sec", "802-11")):
                    kind = "psk"
                else:
                    kind = "serial"
                quoted = m.groupdict().get("q") or ""
                prefix = m.group(0)[:m.start("val") - m.start(0)]
                return prefix + self.token(kind, value) + quoted
            line = rx.sub(repl, line)
        return line

    def _redact_cookie(self, value):
        out = []
        for part in value.split(";"):
            part = part.strip()
            if not part:
                continue
            name, sep, val = part.partition("=")
            if sep and not self._already(val):
                out.append(name + "=" + self.token("cookie", val))
            else:
                out.append(part)
        return "; ".join(out)

    def _redact_ips(self, line):
        def v4(m):
            ip = m.group(0)
            try:
                obj = ipaddress.IPv4Address(ip)
            except ValueError:
                return ip
            if not self.redact_private_ips and (obj.is_private or obj.is_loopback or obj.is_link_local):
                return ip
            return self.token("ip", ip)
        line = RE_IPV4.sub(v4, line)

        def v6(m):
            ip = m.group(0)
            if ip.count(":") < 2 or RE_MAC.fullmatch(ip):
                return ip
            try:
                obj = ipaddress.IPv6Address(ip)
            except ValueError:
                return ip
            if not self.redact_private_ips and (obj.is_loopback or obj.is_link_local):
                return ip
            return self.token("ip6", ip)
        return RE_IPV6.sub(v6, line)

    def text(self, text):
        out = []
        in_key = False
        buf = []
        for raw in text.splitlines(keepends=True):
            if in_key:
                buf.append(raw)
                if RE_PRIVKEY_END.search(raw) or sum(len(x) for x in buf) > MAX_KEY_BLOCK:
                    blob = "".join(buf)
                    out.append(self.token("private-key", blob) + ("\n" if blob.endswith("\n") else ""))
                    in_key = False
                    buf = []
                continue
            if RE_PRIVKEY_BEGIN.search(raw):
                in_key = True
                buf = [raw]
                continue
            out.append(self.line(raw))
        if in_key:
            out.append(self.token("private-key", "".join(buf)) + "\n")
        return "".join(out)


def redact_stream(src, dst, redactor):
    in_key = False
    buf = []
    for raw in src:
        if in_key:
            buf.append(raw)
            if RE_PRIVKEY_END.search(raw) or sum(len(x) for x in buf) > MAX_KEY_BLOCK:
                dst.write(redactor.token("private-key", "".join(buf)) + ("\n" if raw.endswith("\n") else ""))
                in_key = False
                buf = []
            continue
        if RE_PRIVKEY_BEGIN.search(raw):
            in_key = True
            buf = [raw]
            continue
        if len(raw) > MAX_LINE * 2:
            raw = raw[:MAX_LINE] + " <truncated-line>\n"
        dst.write(redactor.line(raw))
    if in_key:
        dst.write(redactor.token("private-key", "".join(buf)) + "\n")
    return redactor.stats


def load_key(args):
    if args.key:
        return bytes.fromhex(args.key.strip())
    if args.key_file:
        data = open(args.key_file, "rb").read().strip()
        try:
            return bytes.fromhex(data.decode("ascii"))
        except (ValueError, UnicodeDecodeError):
            return data
    env = os.environ.get("FZ_REDACT_KEY")
    if env:
        return bytes.fromhex(env.strip())
    raise SystemExit("no key: use --key-file, --key or FZ_REDACT_KEY (never put a real secret in argv)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--key-file")
    ap.add_argument("--key", help="hex key (visible in process list; prefer --key-file)")
    ap.add_argument("--in", dest="infile")
    ap.add_argument("--out", dest="outfile")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--redact-private-ips", action="store_true")
    args = ap.parse_args(argv)
    red = Redactor(load_key(args), redact_private_ips=args.redact_private_ips)
    if args.infile:
        src = open(args.infile, "r", encoding="utf-8", errors="surrogateescape", newline="")
    else:
        src = sys.stdin
    if args.outfile:
        dst = open(args.outfile, "w", encoding="utf-8", errors="surrogateescape", newline="")
    else:
        dst = sys.stdout
    try:
        stats = redact_stream(src, dst, red)
    finally:
        if args.infile:
            src.close()
        if args.outfile:
            dst.close()
    if args.stats:
        for k in sorted(stats):
            print("%s=%d" % (k, stats[k]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
