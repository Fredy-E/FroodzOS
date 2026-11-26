# SPDX-License-Identifier: GPL-2.0-or-later
"""Capture-time redaction for fz_smartlog.

Two modes:

``owner`` (default)
    Keep the owner's raw debugging text (SSIDs, MACs, serials, e-mail), but
    never persist Wi-Fi PSKs, passphrases, account passwords, private keys or
    high-confidence API tokens.  This is the documented local-stick policy.

``redacted``
    The tested streaming redactor: high-entropy secrets are removed,
    low-entropy identifiers become stable keyed pseudonyms
    ``<redacted:kind:12hex>``.  The key comes from ``FZ_REDACT_KEY``,
    ``FZ_REDACT_KEY_FILE`` or ``/run/fz-persist/fz-redact.key``; without one an
    ephemeral per-boot key is generated in memory (never written to the stick).

The implementation is adapted from the tested prototype
``D:\\FroodzOS-build\\tmp\\smartlog-research\\redact\\fz_redact.py``.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import re

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
RE_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")
RE_MAC = re.compile(
    r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b|\b[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}\b")
RE_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
RE_GITHUB = re.compile(
    r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b")
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
RE_AUTH = re.compile(
    r"(?i)(?P<head>(?:proxy-)?authorization)\s*:\s*(?P<scheme>[A-Za-z]+)?\s*(?P<cred>[^\s,;]+)")
RE_COOKIE = re.compile(r"(?i)(?P<head>(?:set-)?cookie)\s*:\s*(?P<val>[^\r\n]+)")
RE_BEARER = re.compile(
    r"(?i)\b(?P<scheme>bearer|basic|token)\s+(?P<cred>[A-Za-z0-9._~+/=-]{8,})")
RE_WPA = re.compile(
    r"(?i)\b(?P<key>psk|passphrase|password|passwd|pwd|pin|wep-key[0-3]?|private_key_passwd|"
    r"wifi-sec\.psk|802-11-wireless-security\.psk)\s*(?P<sep>[=:])\s*"
    r"(?P<q>[\"']?)(?P<val>[^\"'\r\n]*)(?P=q)")
RE_SSID = re.compile(
    r"(?i)\b(?P<key>ssid)\s*(?P<sep>[=:])\s*(?P<q>[\"']?)(?P<val>[^\"'\r\n]*)(?P=q)")
RE_SERIAL = re.compile(
    r"(?i)\b(?P<key>serial(?:\s*number)?|serialno|s/n|iserialnumber|"
    r"id_serial(?:_short)?)\s*(?P<sep>[=:])\s*"
    r"(?P<q>[\"']?)(?P<val>[^\"'\s]+)(?P=q)")
RE_SERIAL_USB = re.compile(r"(?i)\b(?P<key>iserial)\s+\d+\s+(?P<val>\S+)")
RE_HOST = re.compile(
    r"(?i)\b(?P<key>hostname|host\s+name)\s*(?P<sep>[=:])\s*"
    r"(?P<q>[\"']?)(?P<val>[^\"'\s]+)(?P=q)")
RE_USER_UID = re.compile(r"\buid=\d+\((?P<val>[^)]+)\)")
RE_USER_HOME = re.compile(r"(?P<pre>/home/)(?P<val>[^/\s:]+)")
RE_USER_WIN = re.compile(r"(?i)(?P<pre>[A-Za-z]:\\Users\\)(?P<val>[^\\\s]+)")
RE_USER_KV = re.compile(
    r"(?i)\b(?P<key>user|username|login)\s*=\s*(?P<q>[\"']?)(?P<val>[^\"'\s,]+)(?P=q)")
RE_SUDO_PROMPT = re.compile(r"(?i)^(?:\[sudo\]\s*)?password for (?P<user>[^:]+):\s*$")
RE_PASS_PROMPT = re.compile(r"(?i)^(?P<prompt>password|passphrase|pin|token)\s*:\s*$")
RE_FLAG = re.compile(
    r"(?i)(?P<flag>--?(?:password|passwd|pwd|pin|psk|token|secret|api-key|api_key|"
    r"access-key|secret-key))\s+(?P<q>[\"']?)(?P<val>[^\"'\s]+)(?P=q)")
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

SECRET_KEYS = re.compile(
    r"(?i)^(?:psk|passphrase|password|passwd|pwd|pin|wep[-_]?key[0-3]?|"
    r"private[_-]?key|private_key_passwd|api[_-]?key|access[_-]?key|"
    r"secret[_-]?key|token|credential|wifi[-_]sec\.psk|"
    r"802-11-wireless-security\.psk)$")

NEEDLES = (
    "-----BEGIN", "authorization", "cookie", "bearer", "basic", "psk", "ssid",
    "password", "passphrase", "serial", "s/n", "iserial", "hostname", "host name",
    "uid=", "/home/", "\\users\\", "user=", "username=", "login=", "@", "ghp_",
    "gho_", "ghu_", "ghs_", "ghr_", "github_pat_", "akia", "sk-", "xox", "aiza",
    "glpat-", "npm_", "hf_", "eyj", "://",
)


def load_key(environ=None):
    environ = environ or os.environ
    for value in (environ.get("FZ_REDACT_KEY"),):
        if value:
            try:
                return bytes.fromhex(value.strip())
            except ValueError:
                return value.encode("utf-8", "replace")
    for path in (environ.get("FZ_REDACT_KEY_FILE"),
                 "/run/fz-persist/fz-redact.key",
                 "/run/fz-persist/fzlogs/redact.key"):
        if not path:
            continue
        try:
            with open(path, "rb") as fh:
                data = fh.read().strip()
        except OSError:
            continue
        if not data:
            continue
        try:
            return bytes.fromhex(data.decode("ascii"))
        except (ValueError, UnicodeDecodeError):
            return data
    return os.urandom(32)


class Redactor:
    def __init__(self, key=None, mode="redacted", redact_private_ips=False):
        self.mode = "owner" if str(mode).lower() == "owner" else "redacted"
        self.key = key or load_key()
        if len(self.key) < 16:
            # A malformed/weak configured key must not stop the recorder.
            self.key = hashlib.sha256(self.key or os.urandom(16)).digest()
        self.redact_private_ips = redact_private_ips
        self.stats = {}
        self._await_secret = False

    # -- helpers ---------------------------------------------------------
    def _count(self, kind):
        self.stats[kind] = self.stats.get(kind, 0) + 1

    def token(self, kind, value):
        if self.mode == "owner":
            self._count(kind)
            return "%s%s>" % (MARK, kind)
        digest = hmac.new(self.key,
                          value.strip().encode("utf-8", "surrogateescape"),
                          hashlib.sha256).hexdigest()[:TOKEN_HEX]
        self._count(kind)
        return "%s%s:%s>" % (MARK, kind, digest)

    @staticmethod
    def _already(value):
        return MARK in value

    @staticmethod
    def _safe_user(value):
        return value.lower() in SAFE_USERS

    @staticmethod
    def _safe_host(value):
        return value.lower() in SAFE_HOSTS

    # -- owner mode: only hard secrets ----------------------------------
    def owner_text(self, text):
        try:
            return self._owner_text(text)
        except Exception:
            self._count("redaction-error")
            return "%sredaction-error>" % MARK

    def _owner_text(self, text):
        out = []
        in_key = False
        buf = []
        for raw in text.splitlines(keepends=True):
            if in_key:
                buf.append(raw)
                if RE_PRIVKEY_END.search(raw) or sum(len(x) for x in buf) > MAX_KEY_BLOCK:
                    out.append(self.token("private-key", "".join(buf)) +
                               ("\n" if raw.endswith("\n") else ""))
                    in_key = False
                    buf = []
                continue
            if RE_PRIVKEY_BEGIN.search(raw):
                in_key = True
                buf = [raw]
                continue
            out.append(self._owner_line(raw))
        if in_key:
            out.append(self.token("private-key", "".join(buf)) + "\n")
        return "".join(out)

    def _owner_line(self, raw):
        newline = ""
        line = raw
        if line.endswith("\n"):
            line, newline = line[:-1], "\n"
        if len(line) > MAX_LINE:
            line = line[:MAX_LINE] + " <truncated-line>"
        if RE_SUDO_PROMPT.match(line) or RE_PASS_PROMPT.match(line):
            self._await_secret = True
            return line + newline
        if self._await_secret:
            self._await_secret = False
            if line.strip() and not line.lstrip().startswith(("#", "$", ">")):
                return self.token("typed-secret", line) + newline
        m = RE_AUTH.search(line)
        if m and not self._already(m.group("cred")):
            line = line[:m.start("cred")] + self.token("auth", m.group("cred")) + line[m.end("cred"):]
        m = RE_COOKIE.search(line)
        if m and not self._already(m.group("val")):
            line = line[:m.start("val")] + self.token("cookie", m.group("val")) + line[m.end("val"):]
        line = RE_URL_USERINFO.sub(
            lambda x: x.group("scheme") + self.token("url-credential", x.group("userinfo")) + "@", line)
        line = RE_BEARER.sub(
            lambda x: x.group("scheme") + " " + self.token("bearer", x.group("cred")), line)
        for kind, rx in TOKEN_PATTERNS:
            line = rx.sub(lambda x, k=kind: self.token(k, x.group(0)), line)
        line = RE_WPA.sub(self._owner_key_value, line)
        line = RE_FLAG.sub(self._owner_flag, line)
        return line + newline

    def _owner_flag(self, m):
        value = m.group("val")
        if not value or self._already(value):
            return m.group(0)
        prefix = m.group(0)[:m.start("val") - m.start(0)]
        return prefix + self.token("typed-secret", value)

    def _owner_key_value(self, m):
        value = m.group("val")
        if not value or self._already(value):
            return m.group(0)
        prefix = m.group(0)[:m.start("val") - m.start(0)]
        quoted = m.groupdict().get("q") or ""
        return prefix + self.token("psk", value) + quoted

    # -- redacted mode: the full tested filter ---------------------------
    def line(self, raw):
        if self.mode == "owner":
            try:
                return self._owner_line(raw)
            except Exception:
                self._count("redaction-error")
                return "%sredaction-error>\n" % MARK
        try:
            return self._line(raw)
        except Exception:
            self._count("redaction-error")
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
                line = (line[:prompt.start("user")] + self.token("user", user) +
                        line[prompt.end("user"):])
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
            value = ((scheme + " " + self.token(kind, cred)) if scheme
                     else self.token(kind, cred))
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
        line = RE_FLAG.sub(self._redact_flag, line)
        line = RE_EMAIL.sub(lambda x: self.token("email", x.group(0)), line)
        line = RE_MAC.sub(lambda x: self.token("mac", x.group(0)), line)
        line = RE_USER_UID.sub(self._redact_uid, line)
        line = RE_USER_HOME.sub(self._redact_home, line)
        line = RE_USER_WIN.sub(self._redact_win, line)
        line = RE_USER_KV.sub(self._redact_user_kv, line)
        line = self._redact_ips(line)
        return line + newline

    def _redact_flag(self, m):
        value = m.group("val")
        if not value or self._already(value):
            return m.group(0)
        prefix = m.group(0)[:m.start("val") - m.start(0)]
        quoted = m.groupdict().get("q") or ""
        return prefix + self.token("typed-secret", value) + quoted

    def _redact_uid(self, m):
        uid = re.search(r"\d+", m.group(0)).group(0)
        val = m.group("val")
        return "uid=" + uid + "(" + (val if self._safe_user(val) else self.token("user", val)) + ")"

    def _redact_home(self, m):
        val = m.group("val")
        return m.group("pre") + (val if self._safe_user(val) else self.token("user", val))

    def _redact_win(self, m):
        val = m.group("val")
        return m.group("pre") + (val if self._safe_user(val) else self.token("user", val))

    def _redact_user_kv(self, m):
        val = m.group("val")
        return m.group("key") + "=" + (val if self._safe_user(val) else self.token("user", val))

    def _redact_key_values(self, line):
        for rx in (RE_WPA, RE_SSID, RE_SERIAL, RE_SERIAL_USB, RE_HOST):
            line = rx.sub(self._redact_kv, line)
        return line

    def _redact_kv(self, m):
        value = m.group("val")
        if not value or self._already(value):
            return m.group(0)
        key = m.group("key")
        lower = key.lower()
        if lower == "ssid":
            kind = "ssid"
        elif lower in ("hostname", "host name"):
            if self._safe_host(value):
                return m.group(0)
            kind = "host"
        elif lower == "iserial":
            kind = "serial"
        elif lower.startswith(("psk", "passphrase", "password", "wep-key",
                                "private_key_passwd", "wifi-sec", "802-11")):
            kind = "psk"
        else:
            kind = "serial"
        quoted = m.groupdict().get("q") or ""
        prefix = m.group(0)[:m.start("val") - m.start(0)]
        return prefix + self.token(kind, value) + quoted

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
            if not self.redact_private_ips and (
                    obj.is_private or obj.is_loopback or obj.is_link_local):
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

    # -- whole text / structured records ---------------------------------
    def text(self, text):
        if self.mode == "owner":
            return self.owner_text(text)
        try:
            return self._text(text)
        except Exception:
            self._count("redaction-error")
            return "%sredaction-error>\n" % MARK

    def _text(self, text):
        out = []
        in_key = False
        buf = []
        for raw in text.splitlines(keepends=True):
            if in_key:
                buf.append(raw)
                if RE_PRIVKEY_END.search(raw) or sum(len(x) for x in buf) > MAX_KEY_BLOCK:
                    blob = "".join(buf)
                    out.append(self.token("private-key", blob) +
                               ("\n" if blob.endswith("\n") else ""))
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

    def value(self, key, value):
        """Redact one structured value (journal field, plugin record field)."""
        if not isinstance(value, str):
            return value
        if SECRET_KEYS.match(str(key)):
            return self.token("field", value)
        return self.text(value).rstrip("\n")

    def record(self, record):
        if isinstance(record, dict):
            return {k: self.record(v) if isinstance(v, (dict, list)) else self.value(k, v)
                    for k, v in record.items()}
        if isinstance(record, list):
            return [self.record(v) for v in record]
        return record


def redact_stream(src, dst, redactor):
    in_key = False
    buf = []
    for raw in src:
        if in_key:
            buf.append(raw)
            if RE_PRIVKEY_END.search(raw) or sum(len(x) for x in buf) > MAX_KEY_BLOCK:
                dst.write(redactor.token("private-key", "".join(buf)) +
                          ("\n" if raw.endswith("\n") else ""))
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
