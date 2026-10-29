#!/bin/bash
# Build, check and publish the PORTABLE PosterFox -- the tarball for people who do not run PosterChanOS -- as a GitHub
# release of the PosterFox repository (loblawbob873-svg/posterfox). Run on server1 after tools/release.sh has
# published the Gentoo package; it builds the SAME version and revision.
#
#   tools/portable-release.sh            # the version in posterchanai's overlay
#   tools/portable-release.sh 159.0 10   # or say which
#
# Steps, each stopping the run on failure with nothing published:
#   1. assemble PosterFox's files (tools/assemble.py), as the Gentoo release does;
#   2. build on the VM as an unprivileged user (tools/portable-build.sh: Mozilla's toolchain and sysroot, ~1-2 h);
#   3. check it with the release check (tools/smoke.py, the same checks as the Gentoo package);
#   4. publish posterfox-<PV>-r<REV>-linux-x86_64.tar.xz + .sha256 to the release `v<PV>-r<REV>`, marked latest.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PCAI="${POSTERCHANAI:-$HOME/posterchanai}"
VM=${POSTERFOX_VM:-"-J nas.lan root@192.168.122.32"}
REPO=${POSTERFOX_GITHUB:-loblawbob873-svg/posterfox}
LOG=$HOME/.cache/posterfox/portable.log; mkdir -p "$(dirname "$LOG")"
exec 9>"$HOME/.cache/posterfox/portable.lock"; flock -n 9 || { echo "another portable release is running"; exit 1; }
vm() { # shellcheck disable=SC2086
	ssh -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=60 $VM "$@"; }
say() { echo "$(date +%T) $*" | tee -a "$LOG"; }

if [ $# -ge 2 ]; then PV=$1; REV=$2; else
	EB=$(ls "$PCAI"/os/overlay/www-client/posterfox/posterfox-*.ebuild | sort -V | tail -1)
	B=$(basename "$EB" .ebuild); PV=${B#posterfox-}; PV=${PV%-r*}; REV=${B##*-r}
fi
NAME="posterfox-$PV-r$REV-linux-x86_64.tar.xz"
say "portable PosterFox $PV-r$REV"

say "assemble"; python3 "$HERE/tools/assemble.py" --posterchanai "$PCAI" >>"$LOG" 2>&1
IN=/var/tmp-build/portable-in OUTD=/var/tmp-build/portable-out
# The build user, its toolchains (~/.mozbuild, several GB) and the test user live under /var/tmp-build, which the ISO
# excludes, and both users are removed at the end: this VM's disk is what PosterChanOS images are made from.
P=/var/tmp-build/portable
cleanup() { vm "userdel pfbuild 2>/dev/null; userdel posterfoxtest 2>/dev/null; rm -rf /var/tmp-build/portable-smoke" || true; }
trap cleanup EXIT
vm "rm -rf $IN $OUTD; mkdir -p $IN/tools $OUTD $P; id pfbuild >/dev/null 2>&1 || useradd -d $P/home -m pfbuild; \
    id posterfoxtest >/dev/null 2>&1 || useradd -d /var/tmp-build/portable-smoke-home -m posterfoxtest; chown pfbuild $P"
tar -C "$HERE" -cf - tools/portable-build.sh tools/portable_layout.py tools/smoke.py build/files-posterfox \
	| vm "tar -C $IN -xf - && chown -R pfbuild $IN $OUTD"

say "build on the VM (1-2 h)"
if ! vm "su pfbuild -c 'MOZBUILD_STATE_PATH=$P/.mozbuild bash $IN/tools/portable-build.sh $PV $REV $IN/build/files-posterfox $OUTD'" >>"$LOG" 2>&1; then
	say "BUILD FAILED -- nothing published (see $LOG)"; exit 1; fi

say "release check"
SM=/var/tmp-build/portable-smoke
vm "rm -rf $SM && mkdir -p $SM && tar -C $SM -xf $OUTD/$NAME && chown -R posterfoxtest $SM"
if ! vm "su posterfoxtest -c 'cd /tmp && timeout 300 python3 $IN/tools/smoke.py $SM/posterfox/posterfox'" >>"$LOG" 2>&1; then
	say "RELEASE CHECK FAILED -- nothing published (see $LOG)"; vm "rm -rf $SM"; exit 1; fi
vm "rm -rf $SM"

say "publish to github.com/$REPO"
L=$(mktemp -d); trap 'rm -rf "$L"; cleanup' EXIT
scp -q -o BatchMode=yes ${VM/-J /-o ProxyJump=}:"$OUTD/$NAME" ${VM/-J /-o ProxyJump=}:"$OUTD/$NAME.sha256" "$L/"
(cd "$L" && sha256sum -c "$NAME.sha256" >>"$LOG")
TAG="v$PV-r$REV"
NOTES="PosterFox $PV (revision $REV) for any x86-64 Linux: unpack and run \`posterfox/posterfox\`.

Firefox built from Mozilla's source with telemetry compiled out, no Mozilla account, uBlock Origin (every EasyList on), Privacy Badger and PosterChan Passwords, every tab its own container, tabs that sleep after two minutes, and the PosterChan Cyberpunk theme. PosterChanOS installs PosterFox through its own package manager; this tarball is for everywhere else.

PosterFox is not affiliated with or endorsed by Mozilla. Firefox is a trademark of the Mozilla Foundation."
if gh release view "$TAG" -R "$REPO" >/dev/null 2>&1; then
	gh release upload "$TAG" -R "$REPO" --clobber "$L/$NAME" "$L/$NAME.sha256" >>"$LOG"
else
	gh release create "$TAG" -R "$REPO" --latest --title "PosterFox $PV (r$REV)" --notes "$NOTES" "$L/$NAME" "$L/$NAME.sha256" >>"$LOG"
fi
vm "rm -rf $OUTD"
say "published https://github.com/$REPO/releases/tag/$TAG"
