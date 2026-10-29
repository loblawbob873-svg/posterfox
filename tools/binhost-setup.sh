#!/bin/bash
# One-time: the key PosterChanOS binary packages are signed with, and the binhost directory they are served from.
#
#   tools/binhost-setup.sh
#
# The SECRET key lives only on this machine (server1), in its own GnuPG home (~/.config/posterfox/gnupg, 0700), with
# no passphrase so the release timer can sign unattended -- which is why it is a key that can sign nothing but
# PosterChanOS packages, and why it never goes to GitHub or anywhere else. The PUBLIC key is written to
# keys/posterchanos-binpkgs.asc; gentoo.sh installs it on every machine so Portage can check each package.
#
# The binhost is /raid/distfiles/distfiles/posterchan-binpkgs on nas.lan, which router.lan serves as
# https://gentoo.poster.place/posterchan-binpkgs/ (the same tree as the overlay). nas's daily distfiles mirror
# excludes it (admintools servers.py), or `rsync --delete` would remove it every morning.
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
export GNUPGHOME="${POSTERFOX_GNUPG:-$HOME/.config/posterfox/gnupg}"
UID_="PosterChanOS binary packages <binpkgs@poster.place>"
NAS=${NAS:-nas.lan}
DEST=${DEST:-/raid/distfiles/distfiles/posterchan-binpkgs}

install -d -m 0700 "$GNUPGHOME"
if ! gpg --batch --list-secret-keys "$UID_" >/dev/null 2>&1; then
	gpg --batch --pinentry-mode loopback --passphrase '' \
		--quick-generate-key "$UID_" ed25519 sign 5y
	echo "created the signing key"
fi
FPR=$(gpg --batch --with-colons --list-secret-keys "$UID_" | awk -F: '/^fpr:/{print $10; exit}')
mkdir -p "$HERE/keys"
gpg --batch --armor --export "$FPR" > "$HERE/keys/posterchanos-binpkgs.asc"
echo "$FPR" > "$HERE/keys/posterchanos-binpkgs.fpr"
echo "key $FPR -> keys/posterchanos-binpkgs.asc"

ssh -o BatchMode=yes "$NAS" "sudo -n install -d -o \$(id -un) -g \$(id -gn) -m 0755 '$DEST'"
echo "binhost directory $NAS:$DEST"
