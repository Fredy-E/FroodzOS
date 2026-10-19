#!/bin/bash
# Continuation: dst parse + provider lookup + the "invalid path" message.
KSRC=/home/builder/src/ksrc
sed -n '511,560p' "$KSRC/drivers/interconnect/core.c"
