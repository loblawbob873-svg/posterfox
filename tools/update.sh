#!/bin/bash
# PosterFox: follow Mozilla. Regenerate the overlay package from the newest Firefox in the Gentoo tree.
#
#   tools/update.sh [--check] [--posterchanai DIR] [--gentoo DIR] [--distdir DIR]
#
#   --check      only say whether a newer Firefox is available (exit 10 if so, 0 if PosterFox is current) -- for a
#                timer that should not touch anything
#
# What it does, in order (any failure stops it before anything half-done is left in the overlay):
#   1. finds the newest rapid-release firefox-*.ebuild in the Gentoo tree (Gentoo tracks every Mozilla release);
#   2. runs the tests (the generator's edits are asserted, so a changed upstream ebuild fails HERE, by name);
#   3. assembles branding/distribution/theme and writes os/overlay/www-client/posterfox/ in the posterchanai checkout;
#   4. writes the Manifest (fetching the Firefox source, Gentoo's patchset and the pinned uBlock Origin into DISTDIR);
#   5. prints the next step: build the binary package on the build VM (docs/MAINTAINING.md, "Building").
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
PCAI=${POSTERCHANAI:-$HOME/posterchanai}
GENTOO=/var/db/repos/gentoo/www-client/firefox
DISTDIR=${DISTDIR:-$HOME/.cache/posterfox/distfiles}
CHECK=0
PY=${PYTHON:-python3}
while [ $# -gt 0 ]; do
	case "$1" in
		--check) CHECK=1 ;;
		--posterchanai) PCAI=$2; shift ;;
		--gentoo) GENTOO=$2; shift ;;
		--distdir) DISTDIR=$2; shift ;;
		*) echo "unknown option $1" >&2; exit 2 ;;
	esac
	shift
done
PKG="$PCAI/os/overlay/www-client/posterfox"

newest=$("$PY" -c "import importlib.util,sys,pathlib
s=importlib.util.spec_from_file_location('m','$HERE/tools/make-ebuild.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
print(m.newest_firefox(pathlib.Path('$GENTOO')))")
current=$(ls "$PKG"/posterfox-*.ebuild 2>/dev/null | sed -E 's|.*/posterfox-(.*)-r[0-9]+\.ebuild|\1|' | head -1 || true)
echo "newest Firefox in the Gentoo tree: $newest; PosterFox in the overlay: ${current:-none}"
if [ "$CHECK" = 1 ]; then
	[ "${newest%-r*}" = "$current" ] && exit 0 || exit 10
fi

( cd "$HERE" && "$PY" -m pytest -q tests )
"$PY" "$HERE/tools/assemble.py" --posterchanai "$PCAI" >/dev/null
"$PY" "$HERE/tools/make-ebuild.py" --gentoo "$GENTOO" --version "$newest" --out "$PKG"

mkdir -p "$DISTDIR"
EBUILD=$(ls "$PKG"/posterfox-*.ebuild)
# `ebuild manifest` fetches what SRC_URI names into DISTDIR and hashes it. ACCEPT_KEYWORDS: Gentoo keywords new
# Firefox releases ~amd64 first; PosterFox ships what Mozilla released, so it accepts that keyword for itself.
DISTDIR="$DISTDIR" ACCEPT_KEYWORDS="~amd64" PORTAGE_RO_DISTDIRS="" ebuild "$EBUILD" manifest
echo
echo "PosterFox $newest is in $PKG."
echo "Next: commit it in posterchanai, then build the binary package (docs/MAINTAINING.md, \"Building\")."
