#!/bin/bash
# PosterFox, release to installed machines -- the WHOLE update, one command, safe to run from a timer.
#
#   tools/release.sh            do whatever is needed (nothing, if the published binary is already current)
#   tools/release.sh --dry-run  say what would happen and stop
#
# 1. WHAT SHOULD BE PUBLISHED: the newest Firefox in the tree PosterChanOS machines sync (the build VM's), at this
#    repo's REVISION -> posterfox-<PV>-r<REV>. If the binhost already serves exactly that, stop here: nothing to do.
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
STAGE=${STAGE:-$HOME/.cache/posterfox/binhost}
export GNUPGHOME="${POSTERFOX_GNUPG:-$HOME/.config/posterfox/gnupg}"
PY=${PYTHON:-$PCAI/venv-unified/bin/python}
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
LOG=$HOME/.cache/posterfox/release.log; mkdir -p "$(dirname "$LOG")"
say() { echo "[posterfox $(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
die() { say "STOPPED: $*"; exit 1; }
vm() { # shellcheck disable=SC2086
	ssh -o BatchMode=yes -o ConnectTimeout=20 $VM "$@"; }

# One deploy at a time on server1 (and one test run): a gate already running means "try again tomorrow".
if pgrep -f deploy_regression_gate >/dev/null 2>&1 || pgrep -x sync.sh >/dev/null 2>&1; then
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
	say "the binhost already serves $WANT -- nothing to do"; exit 0
fi
[ "$DRY" = 1 ] && { say "dry run: would build and publish $WANT"; exit 0; }

# ---------------------------------------------------------------- 2. the overlay, deployed
PKG="$PCAI/os/overlay/www-client/posterfox"
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
	say "deploying the overlay (sync.sh, full gate)"
	( cd "$PCAI" && systemd-run --user --scope -q -p MemoryHigh=24G -p MemoryMax=30G env PC_GATE_JOBS=6 ./sync.sh ) >>"$LOG" 2>&1 \
		|| die "the deploy did not pass (see $LOG) -- nothing published"
	git -C "$PCAI" push -q github master:main >>"$LOG" 2>&1 || say "warning: the github mirror push failed"
fi

# ---------------------------------------------------------------- 3. build on the VM
say "building $WANT on the build VM"
vm "emaint sync -r posterchan >/dev/null 2>&1; test -f /var/db/repos/posterchan/www-client/posterfox/$WANT.ebuild" \
	|| die "the VM's overlay has no $WANT.ebuild (was the overlay published?)"
vm "rm -rf /var/tmp-build/portage/www-client/posterfox-*; nice -n 10 emerge --oneshot --buildpkgonly --quiet-build =www-client/$WANT" >>"$LOG" 2>&1 \
	|| { vm "tail -40 \$(ls -t /var/tmp-build/portage/www-client/posterfox-*/temp/build.log 2>/dev/null | head -1)" >>"$LOG" 2>&1 || true
	     die "the build failed on the VM (tail in $LOG)"; }
GPKG=$(vm "ls -t /var/cache/binpkgs/www-client/posterfox/$WANT-*.gpkg.tar 2>/dev/null | head -1")
[ -n "$GPKG" ] || die "the VM built nothing at /var/cache/binpkgs/www-client/posterfox/"
vm "rm -rf /var/tmp-build/portage/www-client/posterfox-*"     # 40 GB that must never reach an ISO

# ---------------------------------------------------------------- 4. sign, index, publish
mkdir -p "$STAGE/www-client/posterfox"
# shellcheck disable=SC2086
scp -q -o BatchMode=yes ${VM/-J /-o ProxyJump=}:"$GPKG" "$STAGE/www-client/posterfox/" 2>>"$LOG" \
	|| vm "cat '$GPKG'" > "$STAGE/www-client/posterfox/$(basename "$GPKG")"
F="$STAGE/www-client/posterfox/$(basename "$GPKG")"
FPR=$(cat "$HERE/keys/posterchanos-binpkgs.fpr")
BINPKG_GPG_SIGNING_GPG_HOME="$GNUPGHOME" BINPKG_GPG_SIGNING_KEY="0x$FPR" gpkg-sign "$F" >>"$LOG" 2>&1 || die "signing failed"
tar -tf "$F" | grep -q '\.sig$' || die "the package carries no signature after gpkg-sign"
PKGDIR="$STAGE" emaint binhost --fix >>"$LOG" 2>&1 || die "rebuilding the binhost index failed"
grep -qx "CPV: www-client/$WANT" "$STAGE/Packages" || die "the new index does not list $WANT"
cp "$HERE/keys/posterchanos-binpkgs.asc" "$STAGE/posterchanos-binpkgs.asc"
rsync -a --delete "$STAGE/" "$NAS:$DEST/" || die "publishing to $NAS failed"
for _ in 1 2 3 4 5 6; do   # router.lan serves it over NFS and can briefly cache a stale directory
	curl -fsS "$URL/Packages" 2>/dev/null | grep -qx "CPV: www-client/$WANT" && { say "published $WANT at $URL"; exit 0; }
	sleep 20
done
die "published, but $URL/Packages does not list $WANT yet"
