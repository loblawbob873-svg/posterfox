#!/bin/bash
# The PORTABLE PosterFox (runs on any ordinary x86-64 Linux), built on the build VM by an unprivileged user.
#
#   portable-build.sh <firefox version> <posterfox revision> <files-posterfox dir> <out dir>
#
# Mozilla's own source and Mozilla's own toolchains and sysroot (`--enable-bootstrap`, the way Mozilla builds the Linux
# download), so the binary links only against what every distribution has -- never the Gentoo package's system
# libraries. Gentoo's patches are NOT applied (they adapt Firefox to Gentoo). What PosterFox adds is the same: the
# branding, telemetry compiled out, unsigned app-scope add-ons allowed; tools/portable_layout.py then lays in the
# policies, prefs, theme and add-ons. Writes <out>/posterfox-<PV>-r<REV>-linux-x86_64.tar.xz and its .sha256.
set -euo pipefail
PV="$1" REV="$2" FILES="$3" OUT="$4"
SRC="${POSTERFOX_DISTFILES:-/var/cache/distfiles}/firefox-$PV.source.tar.xz"
W="${POSTERFOX_PORTABLE_DIR:-/var/tmp-build/portable}/$PV"
HERE="$(cd "$(dirname "$0")" && pwd)"
[ -s "$SRC" ] || { echo "no Firefox $PV source at $SRC" >&2; exit 2; }
rm -rf "$W"; mkdir -p "$W" "$OUT"; cd "$W"
echo "== unpack $(date +%T)"; tar xf "$SRC"
cd "firefox-$PV"
cp -r browser/branding/unofficial browser/branding/posterfox
cp -r "$FILES/branding/." browser/branding/posterfox/
cat >mozconfig <<'MOZ'
ac_add_options --enable-application=browser
ac_add_options --enable-bootstrap
ac_add_options --enable-release
ac_add_options --enable-optimize
ac_add_options --disable-debug
ac_add_options --disable-tests
ac_add_options --disable-crashreporter
ac_add_options --disable-updater
ac_add_options --with-branding=browser/branding/posterfox
ac_add_options --with-app-name=posterfox
ac_add_options --with-app-basename=PosterFox
ac_add_options --with-unsigned-addon-scopes=app,system
ac_add_options --allow-addon-sideload
mk_add_options MOZ_OBJDIR=@TOPSRCDIR@/obj
# Telemetry compiled OUT, exactly as the Gentoo package does it (its -telemetry settings).
mk_add_options MOZ_CRASHREPORTER=0
mk_add_options MOZ_DATA_REPORTING=0
mk_add_options MOZ_SERVICES_HEALTHREPORT=0
mk_add_options MOZ_TELEMETRY_REPORTING=0
MOZ
# NOT Gentoo's MACH_BUILD_PYTHON_NATIVE_PACKAGE_SOURCE=none: the bootstrap needs mach to fetch its own Python packages
# (taskcluster) -- with "none" configure stops at "No module named taskcluster.exceptions" (measured 2026-10-29).
export MOZBUILD_STATE_PATH="${MOZBUILD_STATE_PATH:-$HOME/.mozbuild}" MACH_BUILD_PYTHON_NATIVE_PACKAGE_SOURCE=pip
echo "== build $(date +%T)"; nice ./mach --no-interactive build
echo "== package $(date +%T)"; ./mach package
PKG=$(ls obj/dist/posterfox-"$PV"*.linux-x86_64.tar.* | head -1)
[ -n "$PKG" ] || { echo "mach package made no tarball" >&2; exit 1; }
rm -rf "$W/stage"; mkdir -p "$W/stage"; tar xf "$PKG" -C "$W/stage"
python3 "$HERE/portable_layout.py" "$W/stage/posterfox" "$FILES"
NAME="posterfox-$PV-r$REV-linux-x86_64.tar.xz"
tar -C "$W/stage" -cJf "$OUT/$NAME" posterfox
(cd "$OUT" && sha256sum "$NAME" >"$NAME.sha256")
echo "== done $(date +%T) $OUT/$NAME"
