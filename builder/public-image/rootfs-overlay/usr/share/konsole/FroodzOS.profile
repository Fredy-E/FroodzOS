# SPDX-License-Identifier: GPL-2.0-or-later
# FroodzOS Konsole profile: every tab and split runs through fz-term-record, which is a no-op unless fz_record=full.
[General]
Name=FroodzOS Capture
Icon=utilities-terminal
Command=/usr/local/sbin/fz-term-record interactive
Environment=TERM=xterm-256color,COLORTERM=truecolor
SemanticHints=1

[Scrolling]
HistoryMode=2
HistorySize=100000
ScrollBarPosition=1
ScrollFullPage=0
ReflowLines=true

[Terminal Features]
AutoSaveInterval=5000
