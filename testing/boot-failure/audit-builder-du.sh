#!/bin/bash
# Disk audit inside the builder (read-only).
du -x --max-depth=2 /home/builder 2>/dev/null | sort -rn | head -15
echo '=== caches ==='
du -x -sh /home/builder/.cache /var/cache/pacman 2>/dev/null
echo '=== uki dirs ==='
du -x -sh /home/builder/uki* 2>/dev/null | sort -rh | head -20
