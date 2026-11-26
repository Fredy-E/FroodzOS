# SPDX-License-Identifier: GPL-2.0-or-later
# /etc/fz-term-record.bash: installed by the FroodzOS image, sourced from /etc/bash.bashrc.
#
# Install idempotently from build-root.sh (the overlay file list also needs etc/fz-term-record.bash):
#   BR="$BASE/merged/etc/bash.bashrc"
#   sudo grep -q 'fz-term-record.bash' "$BR" || printf '%s\n' \
#       '# FroodzOS terminal capture (armed only by fz_record=full)' \
#       '[ -r /etc/fz-term-record.bash ] && . /etc/fz-term-record.bash' | sudo tee -a "$BR" >/dev/null
#
# When fz_record=full is on the kernel command line, every interactive bash on a terminal replaces itself with
# fz-term-record once, and the inner shell installs the command sidecar below. The environment guard and the /proc
# ancestor guard stop a second recorder after sudo -i, su -, a nested bash, tmux or ssh. When the option is absent this
# file costs one grep (or one call to fz-record-on) and returns.

fz_term_armed() {
    local on=${FZ_RECORD_ON:-/usr/local/sbin/fz-record-on}
    if [ -x "$on" ]; then "$on" >/dev/null 2>&1; return $?; fi
    grep -qw 'fz_record=full' "${FZ_CMDLINE:-/proc/cmdline}" 2>/dev/null
}

fz_term_under_recorder() {
    local p=${PPID:-0} c
    while [ "${p:-0}" -gt 1 ] 2>/dev/null; do
        c=$(cat "${FZ_TERM_PROC:-/proc}/$p/comm" 2>/dev/null) || return 1
        case "$c" in script|fz-term-record|fz-termwrap|asciinema*) return 0 ;; esac
        p=$(awk '/^PPid:/{print $2; exit}' "${FZ_TERM_PROC:-/proc}/$p/status" 2>/dev/null)
        case "$p" in ''|*[!0-9]*) return 1 ;; esac
    done
    return 1
}

fz_term_nested_shell() {
    local p=${PPID:-0} c
    while [ "${p:-0}" -gt 1 ] 2>/dev/null; do
        c=$(cat "${FZ_TERM_PROC:-/proc}/$p/comm" 2>/dev/null) || return 1
        case "$c" in
            script|fz-term-record|fz-termwrap|asciinema*) return 1 ;;
            bash|dash|sh|zsh|fish|ksh) return 0 ;;
        esac
        p=$(awk '/^PPid:/{print $2; exit}' "${FZ_TERM_PROC:-/proc}/$p/status" 2>/dev/null)
        case "$p" in ''|*[!0-9]*) return 1 ;; esac
    done
    return 1
}

fz_term_log_cmd() {
    local rc=$? start end hist num cmd cwd
    start=${FZ_TERM_T0:-}
    FZ_TERM_T0=
    end=${EPOCHREALTIME:-}
    [ -n "$start" ] && [ -n "$end" ] && [ -n "${FZ_TERM_CMDS:-}" ] || return "$rc"
    hist=$(HISTTIMEFORMAT= builtin history 1 2>/dev/null) || return "$rc"
    hist=${hist#"${hist%%[![:space:]]*}"}
    num=${hist%% *}
    cmd=${hist#* }
    cmd=${cmd#"${cmd%%[![:space:]]*}"}
    case "$num" in ''|*[!0-9]*) return "$rc" ;; esac
    [ -n "$cmd" ] && [ "$num" != "${FZ_LAST_HIST:-}" ] || return "$rc"
    FZ_LAST_HIST=$num
    cmd=${cmd//$'\t'/ }
    cmd=${cmd//$'\n'/ }
    cwd=${PWD//$'\t'/ }
    cwd=${cwd//$'\n'/ }
    FZ_TERM_SEQ=$(( ${FZ_TERM_SEQ:-0} + 1 ))
    if printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$FZ_TERM_SEQ" "$start" "$end" "$rc" "$cwd" "$cmd" \
        >> "${FZ_TERM_CMDS}" 2>/dev/null; then
        printf '\033]6973;FZ;E;%s;%s;%s\a' "$FZ_TERM_SEQ" "$rc" "$end"
    fi
    return "$rc"
}

case $- in *i*) ;; *) return 0 2>/dev/null || exit 0 ;; esac

if [ -n "${FZ_TERM_ACTIVE:-}" ] && [ -n "${FZ_TERM_DIR:-}" ]; then
    fz_term_nested_shell && { return 0 2>/dev/null || exit 0; }
    if [ -z "${FZ_TERM_HOOKED:-}" ]; then
        FZ_TERM_HOOKED=1
        FZ_TERM_SEQ=$(( ${FZ_TERM_SEQ:-0} + $$ * 1000 ))
        FZ_TERM_T0=
        FZ_LAST_HIST=$(HISTTIMEFORMAT= builtin history 1 2>/dev/null)
        FZ_LAST_HIST=${FZ_LAST_HIST#"${FZ_LAST_HIST%%[![:space:]]*}"}
        FZ_LAST_HIST=${FZ_LAST_HIST%% *}
        case "$FZ_LAST_HIST" in ''|*[!0-9]*) FZ_LAST_HIST= ;; esac
        PS0='\e]6973;FZ;S;${FZ_TERM_T0:=${EPOCHREALTIME}}\a'"${PS0:-}"
        case "$(declare -p PROMPT_COMMAND 2>/dev/null)" in
            'declare -a'*) PROMPT_COMMAND=(fz_term_log_cmd "${PROMPT_COMMAND[@]}") ;;
            *) PROMPT_COMMAND="fz_term_log_cmd${PROMPT_COMMAND:+;$PROMPT_COMMAND}" ;;
        esac
        if [ -z "$(trap -p EXIT 2>/dev/null)" ]; then
            trap 'fz_term_log_cmd' EXIT
        fi
    fi
    return 0 2>/dev/null || exit 0
fi

[ -n "${FZ_TERM_DISABLE:-}" ] && { return 0 2>/dev/null || exit 0; }
[ -t 0 ] && [ -t 1 ] || { return 0 2>/dev/null || exit 0; }
fz_term_armed || { return 0 2>/dev/null || exit 0; }
fz_term_under_recorder && { return 0 2>/dev/null || exit 0; }

fz_mode=interactive
shopt -q login_shell && fz_mode=login
exec "${FZ_TERM_RECORD:-/usr/local/sbin/fz-term-record}" "$fz_mode"
