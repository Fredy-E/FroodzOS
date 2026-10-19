#!/bin/bash
# Task 3.1/3.3: project signing keys + signed overlay repo (ADR-7, 2026-10-08)
# - Offline master key material generated here for convenience, exported to D: for
#   the user to archive OFF the machine; the build key signs packages in the builder.
# - Repository DBs are signed too (fixing the ALARM unsigned-DB gap).
set -euo pipefail
REPO=/srv/cachyos-arm64/aarch64
KEYDIR=/home/builder/project-keys
mkdir -p "$REPO" "$KEYDIR"
export GNUPGHOME="$KEYDIR"
chmod 700 "$KEYDIR"

if ! gpg --list-keys "CachyOS-ARM64 Project Master" >/dev/null 2>&1; then
    gpg --batch --pinentry-mode loopback --passphrase '' \
        --quick-generate-key 'CachyOS-ARM64 Project Master <master@local>' ed25519 sign 0
    gpg --batch --pinentry-mode loopback --passphrase '' \
        --quick-add-key "$(gpg --list-keys --with-colons 'master@local' | awk -F: '/^fpr/{print $10; exit}')" ed25519 sign 1y
fi
MASTER=$(gpg --list-keys --with-colons 'master@local' | awk -F: '/^fpr/{print $10; exit}')
echo "MASTER_KEY=$MASTER"

# export master public + private for the user's offline archive
gpg --armor --export 'master@local' > /mnt/d/CachyOS-ARM64/keys/offline/master-public.asc
gpg --armor --export-secret-keys 'master@local' > /mnt/d/CachyOS-ARM64/keys/offline/master-SECRET-backup.asc
chmod 644 /mnt/d/CachyOS-ARM64/keys/offline/*.asc

# build key (builder's existing G1 key) — import into the project keyring and lsign
export GNUPGHOME=/home/builder/.gnupg
BUILDKEY=$(gpg --list-keys --with-colons 'builder@local' | awk -F: '/^fpr/{print $10; exit}')
gpg --armor --export "$BUILDKEY" > /tmp/buildkey.asc
export GNUPGHOME="$KEYDIR"
gpg --import /tmp/buildkey.asc
gpg --batch --yes --lsign-key "$BUILDKEY"
echo "BUILD_KEY=$BUILDKEY"

# collect the two packages we have and build a SIGNED repo DB
cp /home/builder/g1/cachyos-arm64-hello-*.pkg.tar.* "$REPO/" 2>/dev/null || true
cp /home/builder/pkg-linux/linux-cachyos-arm64-*.pkg.tar.* "$REPO/" 2>/dev/null || true
cd "$REPO"
rm -f cachyos-arm64.db* cachyos-arm64.files*
shopt -s nullglob
PKGS=(./*.pkg.tar.xz ./*.pkg.tar.zst)
[ ${#PKGS[@]} -gt 0 ] || { echo "no packages found in $REPO" >&2; exit 1; }
repo-add --sign --key "$MASTER" --verify cachyos-arm64.db.tar.gz "${PKGS[@]}"
ls -la
echo "=== verify DB signature ==="
gpg --verify cachyos-arm64.db.tar.gz.sig cachyos-arm64.db.tar.gz 2>&1 | head -3
echo REPO_GATE_DONE
