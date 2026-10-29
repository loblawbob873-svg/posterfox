#!/usr/bin/env python3
"""Lay PosterFox's own files into an unpacked PORTABLE build (`./mach package` output, the `posterfox/` directory).

    tools/portable_layout.py <unpacked posterfox/> <build/files-posterfox> [--xpi-dir DIR]

The same files the Gentoo package installs (tools/make-ebuild.py posterfox_distribution), placed relative to the
browser instead of /usr/lib64/posterfox -- a portable tarball can be unpacked anywhere. Two things differ, both because
of that:
  * policies.json installs the AMO-signed add-ons from addons.mozilla.org (their `latest` address), not from a file
    path that only exists on PosterChanOS; they then update themselves from AMO as on any Firefox.
  * the window-button GTK setting is not applied (the Gentoo package does it in its launcher script; a tarball's
    `posterfox` binary is started directly).
"""
import json
import pathlib
import shutil
import sys

AMO = {
    "uBlock0@raymondhill.net": "ublock-origin",
    "jid1-MnnxcxisBPnSXQ@jetpack": "privacy-badger17",
    "passwords@poster.place": "posterchan-passwords",
}


def portable_policies(policies: dict) -> dict:
    p = json.loads(json.dumps(policies))
    for aid, s in p["policies"].get("ExtensionSettings", {}).items():
        if aid in AMO and "install_url" in s:
            s["install_url"] = "https://addons.mozilla.org/firefox/downloads/latest/%s/latest.xpi" % AMO[aid]
        elif str(s.get("install_url", "")).startswith("file://"):
            raise SystemExit("policies.json installs %s from a local path the portable build does not have" % aid)
    return p


def layout(root: pathlib.Path, files: pathlib.Path) -> None:
    root, files = pathlib.Path(root), pathlib.Path(files)
    if not (root / "posterfox").exists():
        raise SystemExit("%s is not an unpacked PosterFox (no posterfox binary)" % root)
    d = files / "distribution"
    (root / "distribution").mkdir(exist_ok=True)
    shutil.copy(d / "distribution.ini", root / "distribution" / "distribution.ini")
    pol = portable_policies(json.loads((d / "policies.json").read_text()))
    (root / "distribution" / "policies.json").write_text(json.dumps(pol, indent=2) + "\n")
    (root / "browser" / "defaults" / "preferences").mkdir(parents=True, exist_ok=True)
    shutil.copy(d / "posterfox-prefs.js", root / "browser" / "defaults" / "preferences" / "posterfox-prefs.js")
    (root / "defaults" / "pref").mkdir(parents=True, exist_ok=True)
    shutil.copy(d / "autoconfig.js", root / "defaults" / "pref" / "autoconfig.js")
    shutil.copy(d / "posterfox.cfg", root / "posterfox.cfg")
    (root / "posterchan").mkdir(exist_ok=True)
    shutil.copy(d / "posterfox-chrome.css", root / "posterchan" / "posterfox-chrome.css")
    ext = root / "browser" / "extensions"
    ext.mkdir(parents=True, exist_ok=True)
    shutil.copy(files / "extensions" / "posterchan-cyberpunk.xpi", ext / "cyberpunk-theme@poster.place.xpi")
    shutil.copy(files / "extensions" / "posterfox-tab-containers.xpi", ext / "tab-containers@posterfox.poster.place.xpi")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    layout(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
