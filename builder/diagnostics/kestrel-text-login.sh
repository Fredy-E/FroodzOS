#!/bin/bash
# Local diagnostic getty login program; no account or password files changed.
export HOME=/root USER=root LOGNAME=root
export PATH=/usr/local/sbin:/usr/local/bin:/usr/bin
export TERM=${TERM:-linux}
cd /root || cd /
exec /usr/bin/bash --noprofile --rcfile /usr/local/lib/kestrel-text-bashrc -i
