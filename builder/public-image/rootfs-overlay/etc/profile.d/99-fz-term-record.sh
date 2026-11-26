#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# Fallback for login shells. On Arch /etc/profile already sources /etc/bash.bashrc for interactive bash, so this is
# normally a no-op; it exists for images whose /etc/profile does not, and it never wraps a non-bash shell into bash.
[ -n "${BASH_VERSION:-}" ] || return 0 2>/dev/null || exit 0
[ -r /etc/fz-term-record.bash ] && . /etc/fz-term-record.bash
return 0 2>/dev/null || exit 0
