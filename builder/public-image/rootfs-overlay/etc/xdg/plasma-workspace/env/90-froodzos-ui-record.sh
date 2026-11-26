# SPDX-License-Identifier: GPL-2.0-or-later
# FroodzOS: enable the curated Qt/KDE logging rules only on a full recording boot.
#
# startplasma sources this file for the session tree. With fz_record=full it points Qt at
# /etc/xdg/QtProject/qtlogging-froodzos-full.ini (QT_LOGGING_CONF outranks the default ini).
# On a normal boot the variable is not exported, so categorized debug output stays off.
# The root fz-ui-capture service also links the same rules to /etc/xdg/QtProject/qtlogging.ini
# before SDDM starts, which covers the greeter and systemd user units even if this snippet is
# not reached. Test hooks: FZ_CMDLINE, FZ_RECORD_ON, FZ_QT_FULL.
FZ_QT_FULL=${FZ_QT_FULL:-/etc/xdg/QtProject/qtlogging-froodzos-full.ini}
FZ_RECORD_ON=${FZ_RECORD_ON:-/usr/local/sbin/fz-record-on}
_fz_on=0
if [ -n "${FZ_CMDLINE:-}" ]; then
    if [ -f "$FZ_CMDLINE" ]; then _fz_cmd=$(cat "$FZ_CMDLINE" 2>/dev/null); else _fz_cmd=$FZ_CMDLINE; fi
    case " $_fz_cmd " in *" fz_record=full "*) _fz_on=1 ;; esac
elif [ -x "$FZ_RECORD_ON" ]; then
    "$FZ_RECORD_ON" >/dev/null 2>&1 && _fz_on=1
else
    _fz_cmd=$(cat /proc/cmdline 2>/dev/null)
    case " $_fz_cmd " in *" fz_record=full "*) _fz_on=1 ;; esac
fi
if [ "$_fz_on" = 1 ] && [ -r "$FZ_QT_FULL" ]; then
    export QT_LOGGING_CONF="$FZ_QT_FULL"
elif [ "${QT_LOGGING_CONF:-}" = "$FZ_QT_FULL" ]; then
    unset QT_LOGGING_CONF
fi
unset _fz_on _fz_cmd
