#!/bin/bash
# PosterFox, release to installed machines -- the WHOLE update, one command, safe to run from a timer.
#
#   tools/release.sh            do whatever is needed (nothing, if the published binary is already current)
#   tools/release.sh --dry-run  say what would happen and stop
#
# 1. WHAT SHOULD BE PUBLISHED: the newest Firefox in the tree PosterChanOS machines sync (the build VM's), at this
#    repo's REVISION -> posterfox-<PV>-r<REV>. If the binhost already serves exactly that AND it was linked against the
#    libraries Gentoo's binhost serves today (tools/stale_deps.py), stop here: nothing to do. A library that moved
#    (nas.lan's 06:00 sync brings icu 79, a new ffmpeg ABI...) makes Portage refuse our binary on every machine that
#    updates and compile Firefox from source instead, so that is rebuilt too -- same version, a new build of it.
# 2. OVERLAY: regenerate www-client/posterfox in the posterchanai checkout (tests first; a changed Gentoo ebuild stops
#    here by name), commit it, and DEPLOY with sync.sh like any other change -- that publishes the overlay the VM and
#    every machine sync. Skipped when the overlay already has that ebuild.
# 3. BUILD on the PosterChanOS build VM: sync, then `emerge --oneshot --buildpkgonly` (never a plain emerge there: the
#    VM's disk becomes the ISO). distcc spreads the C/C++ over nas and server1 (the VM's posterfox package.env).
# 4. SIGN on this machine (the key never leaves it), rebuild the binhost index, publish to nas, and confirm the
#    published index lists the package with a signature.
#
# Any step that fails stops the run with its reason; nothing is published unless it was built AND signed. Log:
# ~/.cache/posterfox/release.log. The timer: tools/posterfox-release.{service,timer} (daily).
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
PCAI=${POSTERCHANAI:-$HOME/posterchanai}
VM=${POSTERFOX_VM:-"-J nas.lan root@192.168.122.32"}
NAS=${NAS:-nas.lan}
DEST=${DEST:-/raid/distfiles/distfiles/posterchan-binpkgs}
URL=${BINHOST_URL:-https://gentoo.poster.place/posterchan-binpkgs}
GENTOO_BINHOST=${GENTOO_BINHOST:-https://gentoo.poster.place/releases/amd64/binpackages/23.0/x86-64}
STAGE=${STAGE:-$HOME/.cache/posterfox/binhost}
export GNUPGHOME="${POSTERFOX_GNUPG:-$HOME/.config/posterfox/gnupg}"
PY=${PYTHON:-$PCAI/venv-unified/bin/python}
PYTHON_SYS=${PYTHON_SYS:-/usr/bin/python3}   # the system Python: Portage's modules are not in the app's venv
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
LOG=$HOME/.cache/posterfox/release.log; mkdir -p "$(dirname "$LOG")"
say() { echo "[posterfox $(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
die() { say "STOPPED: $*"; exit 1; }
# set -e ends the run at any failing command; say where, or a timer run just stops with nothing in the log.
trap 'say "STOPPED: unexpected failure at line $LINENO (exit $?)"' ERR
vm() { # shellcheck disable=SC2086
	ssh -o BatchMode=yes -o ConnectTimeout=20 $VM "$@"; }

# One deploy at a time on server1 (and one test run): a gate already running means "try again tomorrow".
# A sync.sh whose only child is its post-deploy APK waiter (scripts/wait_apk_build.sh, up to an hour of CI) is a
# finished deploy, not a running one.
deploying() {
	# Anchored: an unanchored pattern also matches any shell whose command line merely mentions the gate.
	pgrep -f '^[^ ]*python[^ ]* ([^ ]+ )*scripts/deploy_regression_gate[.]py' >/dev/null 2>&1 && return 0
	local p
	for p in $(pgrep -x sync.sh); do pgrep -P "$p" -f wait_apk_build >/dev/null 2>&1 || return 0; done
	return 1
}
if deploying; then
	say "a deploy is running -- not starting one beside it"; exit 0
fi

# ---------------------------------------------------------------- 1. what should be published
TREE=$(mktemp -d); trap 'rm -rf "$TREE"' EXIT
vm 'emaint sync -r gentoo >/dev/null 2>&1; tar -cf - -C /var/db/repos/gentoo/www-client firefox' | tar -xf - -C "$TREE" \
	|| die "could not read the build VM's Gentoo tree"
PV=$("$PY" -c "import importlib.util,pathlib;s=importlib.util.spec_from_file_location('m','$HERE/tools/make-ebuild.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);print(m.newest_firefox(pathlib.Path('$TREE/firefox')).split('-r')[0])")
REV=$(cat "$HERE/REVISION")
WANT="posterfox-$PV-r$REV"
say "want $WANT"
if curl -fsS "$URL/Packages" 2>/dev/null | grep -qx "CPV: www-client/$WANT"; then
	MOVED=$("$PY" "$HERE/tools/stale_deps.py" --ours "$URL/Packages" --gentoo "$GENTOO_BINHOST/Packages" \
		--cpv "www-client/$WANT" 2>>"$LOG") || die "could not compare $WANT with Gentoo's binhost (see $LOG)"
	[ -z "$MOVED" ] && { say "the binhost already serves $WANT, built against today's libraries -- nothing to do"; exit 0; }
	say "rebuilding $WANT: Gentoo moved $(echo $MOVED)"
fi
[ "$DRY" = 1 ] && { say "dry run: would build and publish $WANT"; exit 0; }

# ---------------------------------------------------------------- 2. the overlay, deployed
PKG="$PCAI/os/overlay/www-client/posterfox"
vm_has() { vm "emaint sync -r posterchan >/dev/null 2>&1; test -f /var/db/repos/posterchan/www-client/posterfox/$WANT.ebuild"; }
if [ ! -f "$PKG/$WANT.ebuild" ]; then
	[ -z "$(git -C "$PCAI" status --porcelain --untracked-files=no)" ] || die "posterchanai has uncommitted changes -- not touching it"
	PYTHON="$PY" "$HERE/tools/update.sh" --gentoo "$TREE/firefox" --posterchanai "$PCAI" >>"$LOG" 2>&1 \
		|| die "regenerating the ebuild failed (see $LOG)"
	[ -f "$PKG/$WANT.ebuild" ] || die "update.sh did not produce $WANT.ebuild"
	( cd "$PCAI" && "$PY" -m pytest -q tests/test_code_git_ui_and_os.py tests/test_gentoo_packages_exist.py \
		tests/test_overlay_ebuild_versions.py tests/test_overlay_files_change_bumps_the_revision.py ) >>"$LOG" 2>&1 \
		|| die "the overlay checks refused the new ebuild (see $LOG)"
	git -C "$PCAI" add os/overlay/www-client/posterfox
	git -C "$PCAI" commit -q -m "www-client/posterfox: $WANT (posterfox/tools/release.sh)" -- os/overlay/www-client/posterfox
fi
# Committed is not published: the VM (like every machine) only sees what a deploy pushed to the overlay.
if ! vm_has; then
	say "deploying the overlay (sync.sh, full gate)"
	( cd "$PCAI" && systemd-run --user --scope -q -p MemoryHigh=24G -p MemoryMax=30G env PC_GATE_JOBS=6 ./sync.sh ) >>"$LOG" 2>&1 \
		|| die "the deploy did not pass (see $LOG) -- nothing published"
	git -C "$PCAI" push -q github master:main >>"$LOG" 2>&1 || say "warning: the github mirror push failed"
	vm_has || die "deployed, but the VM's overlay still has no $WANT.ebuild"
fi

# ---------------------------------------------------------------- 3. build on the VM
# --buildpkgonly links against what the VM HAS, not what the tree offers: bring every library PosterFox depends on up to
# what Gentoo's binhost serves (binaries only, never a compile), or the new build is stale the day it is published.
say "updating PosterFox's libraries on the build VM"
# Runtime libraries only (--with-bdeps=n: the compiler toolchain stays as it is). Asked first: --usepkgonly cannot be
# used here (it also demands a binary of PosterFox itself), so anything that would COMPILE stops the run by name instead.
DEPS="--oneshot --update --onlydeps --onlydeps-with-rdeps=y --with-bdeps=n --usepkg --getbinpkg =www-client/$WANT"
PLAN=$(vm "emerge -p $DEPS" 2>>"$LOG") || die "could not plan PosterFox's library update on the VM (see $LOG)"
echo "$PLAN" >>"$LOG"
SRC=$(echo "$PLAN" | { grep '^\[ebuild' || true; } | sed 's/^\[ebuild[^]]*\] *//; s/ .*//' | tr '\n' ' ')
[ -z "$SRC" ] || die "updating PosterFox's libraries would compile from source on the VM: $SRC"
if echo "$PLAN" | grep -q '^\[binary'; then
	vm "emerge --quiet $DEPS" >>"$LOG" 2>&1 || die "could not update PosterFox's libraries on the VM (see $LOG)"
fi
say "building $WANT on the build VM"
# The build settings travel ON THIS COMMAND LINE, never in the VM's /etc/portage: the VM's disk becomes the ISO, so a
# package.env entry there shipped to every machine installed from it (found in the 2026-10-29 ISO, with a distcc host
# list naming this LAN). The tree goes to /var/tmp-build (on disk; /var/tmp is a RAM tmpfs), which livecd excludes.
vm "rm -rf /var/tmp-build/portage/www-client/posterfox-*; PORTAGE_TMPDIR=/var/tmp-build MAKEOPTS=\"-j\$(nproc) -l\$(nproc)\" nice -n 10 emerge --oneshot --buildpkgonly --quiet-build =www-client/$WANT" >>"$LOG" 2>&1 \
	|| { vm "tail -40 \$(ls -t /var/tmp-build/portage/www-client/posterfox-*/temp/build.log 2>/dev/null | head -1)" >>"$LOG" 2>&1 || true
	     die "the build failed on the VM (tail in $LOG)"; }
GPKG=$(vm "ls -t /var/cache/binpkgs/www-client/posterfox/$WANT-*.gpkg.tar 2>/dev/null | head -1")
[ -n "$GPKG" ] || die "the VM built nothing at /var/cache/binpkgs/www-client/posterfox/"
vm "rm -rf /var/tmp-build/portage/www-client/posterfox-*"     # 40 GB that must never reach an ISO

# ---------------------------------------------------------------- 3b. use it before anybody gets it
# The built package, unpacked on the VM and started headless as an ordinary user (tools/smoke.py over Marionette): its
# name, policies, add-ons, privacy defaults, window stylesheet, codecs and per-tab containers. Any failure stops here,
# before the package is signed -- "it compiled" is not "it works" (r6 and r7 compiled and could not be installed).
say "checking the built browser"
SMOKE=/var/tmp-build/posterfox-smoke
vm "rm -rf $SMOKE && mkdir -p $SMOKE/pkg $SMOKE/root && tar -xf '$GPKG' -C $SMOKE/pkg && tar -xf \$(ls $SMOKE/pkg/*/image.tar.*) -C $SMOKE/root \
    && (id posterfoxtest >/dev/null 2>&1 || useradd -m posterfoxtest) && chmod -R o+rX $SMOKE" >>"$LOG" 2>&1 \
	|| die "could not unpack the built package on the VM to check it (see $LOG)"
vm "cat > $SMOKE/smoke.py" <"$HERE/tools/smoke.py"
if ! vm "su posterfoxtest -c 'cd /tmp && timeout 300 python3 $SMOKE/smoke.py $SMOKE/root/image/usr/lib64/posterfox/posterfox'" >>"$LOG" 2>&1; then
	vm "rm -rf $SMOKE; userdel -r posterfoxtest 2>/dev/null"; die "the built browser failed its checks (the report is in $LOG) -- nothing published"
fi
# The check's user goes again: the VM's disk becomes the ISO, and an account left here ships to every installed machine.
vm "rm -rf $SMOKE; userdel -r posterfoxtest 2>/dev/null; true"

# ---------------------------------------------------------------- 4. sign, index, publish
mkdir -p "$STAGE/www-client/posterfox"
# A run that stopped after fetching but before signing leaves an UNSIGNED package here; the index below would list it.
for old in "$STAGE"/www-client/posterfox/*.gpkg.tar; do
	[ -e "$old" ] || continue
	tar -tf "$old" | grep -q '\.sig$' || { say "removing an unsigned leftover: $(basename "$old")"; rm -f "$old"; }
done
# shellcheck disable=SC2086
scp -q -o BatchMode=yes ${VM/-J /-o ProxyJump=}:"$GPKG" "$STAGE/www-client/posterfox/" 2>>"$LOG" \
	|| vm "cat '$GPKG'" > "$STAGE/www-client/posterfox/$(basename "$GPKG")"
F="$STAGE/www-client/posterfox/$(basename "$GPKG")"
FPR=$(cat "$HERE/keys/posterchanos-binpkgs.fpr")
# --allow-unsigned: gpkg-sign first VERIFIES the package with this machine's Portage settings and refuses one that has
# no signature yet (which every fresh build is). The lock: Portage's default command takes /run/lock/portage-binpkg-gpg.lock,
# which only root can create; signing is a user job, so the lock lives beside the key.
BINPKG_GPG_SIGNING_BASE_COMMAND="/usr/bin/flock $GNUPGHOME/.sign.lock /usr/bin/gpg --sign --armor [PORTAGE_CONFIG]" \
BINPKG_GPG_SIGNING_GPG_HOME="$GNUPGHOME" BINPKG_GPG_SIGNING_KEY="0x$FPR" \
	gpkg-sign --allow-unsigned "$F" >>"$LOG" 2>&1 || die "signing failed (see $LOG)"
tar -tf "$F" | grep -q '\.sig$' || die "the package carries no signature after gpkg-sign"
# THE INDEX, through Portage's own handler. Two things about this machine's Portage would otherwise drop the package
# from it without a word (measured): it VERIFIES every signed package it reads, with /etc/portage/gnupg, which does not
# hold our key -- so the verify keyring is the release keyring, where the key is trusted; and the `emaint` command-line
# wrapper did nothing at all here (PACKAGES: 0, exit 0) where the same handler, called directly, indexes the package.
BINPKG_GPG_VERIFY_GPG_HOME="$GNUPGHOME" PKGDIR="$STAGE" "$PYTHON_SYS" -c '
import sys
from portage.emaint.modules.binhost.binhost import BinhostHandler
ok, err = BinhostHandler().fix()
sys.exit(0 if ok else 1)' >>"$LOG" 2>&1 || die "rebuilding the binhost index failed (see $LOG)"
grep -qx "CPV: www-client/$WANT" "$STAGE/Packages" || die "the new index does not list $WANT"
for pkg in "$STAGE"/*/*/*.gpkg.tar; do
	tar -tf "$pkg" | grep -q '\.sig$' || die "refusing to publish an unsigned package: $pkg"
done
cp "$HERE/keys/posterchanos-binpkgs.asc" "$STAGE/posterchanos-binpkgs.asc"
# No --delete: a lost or fresh stage directory must never empty the binhost every machine updates from.
rsync -a "$STAGE/" "$NAS:$DEST/" || die "publishing to $NAS failed"
for _ in 1 2 3 4 5 6; do   # router.lan serves it over NFS and can briefly cache a stale directory
	curl -fsS "$URL/Packages" 2>/dev/null | grep -qx "CPV: www-client/$WANT" && { say "published $WANT at $URL"; exit 0; }
	sleep 20
done
die "published, but $URL/Packages does not list $WANT yet"
