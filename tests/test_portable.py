"""The portable PosterFox (tools/portable-build.sh + tools/portable_layout.py): the tarball for people who do not run
PosterChanOS. "do the bundled build for github" (2026-10-29)."""
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import portable_layout as PL  # noqa: E402


def _files(tmp):
    """build/files-posterfox as assemble.py writes it (the real distribution files, stand-in add-ons)."""
    f = tmp / "files"
    shutil.copytree(ROOT / "distribution", f / "distribution")
    (f / "extensions").mkdir()
    for n in ("posterchan-cyberpunk.xpi", "posterfox-tab-containers.xpi"):
        (f / "extensions" / n).write_bytes(b"PK" + n.encode())
    return f


def test_our_files_land_relative_to_the_browser(tmp_path):
    root = tmp_path / "posterfox"
    root.mkdir()
    (root / "posterfox").write_text("#!/bin/sh\n")
    PL.layout(root, _files(tmp_path))
    for p in ("distribution/distribution.ini", "distribution/policies.json", "browser/defaults/preferences/posterfox-prefs.js",
              "defaults/pref/autoconfig.js", "posterfox.cfg", "posterchan/posterfox-chrome.css",
              "browser/extensions/cyberpunk-theme@poster.place.xpi", "browser/extensions/tab-containers@posterfox.poster.place.xpi"):
        assert (root / p).exists(), p
    pol = json.loads((root / "distribution/policies.json").read_text())["policies"]
    urls = {k: v["install_url"] for k, v in pol["ExtensionSettings"].items()}
    assert not any(u.startswith("file://") for u in urls.values()), urls          # no PosterChanOS-only paths
    assert urls["passwords@poster.place"] == "https://addons.mozilla.org/firefox/downloads/latest/posterchan-passwords/latest.xpi"
    assert urls["uBlock0@raymondhill.net"].endswith("/ublock-origin/latest.xpi")
    assert pol["DisableTelemetry"] and pol["DisableFirefoxAccounts"]               # everything else carried as is
    assert pol["3rdparty"]["Extensions"]["uBlock0@raymondhill.net"]["toOverwrite"]["filterLists"]


def test_a_local_only_add_on_is_refused_not_shipped_broken():
    pol = {"policies": {"ExtensionSettings": {"x@y": {"install_url": "file:///usr/lib64/posterfox/x.xpi"}}}}
    try:
        PL.portable_policies(pol)
    except SystemExit as e:
        assert "x@y" in str(e)
    else:
        raise AssertionError("an add-on only PosterChanOS has was carried into the portable build")


def test_the_build_is_mozillas_toolchain_with_telemetry_out():
    sh = (ROOT / "tools/portable-build.sh").read_text()
    for opt in ("--enable-bootstrap", "--with-branding=browser/branding/posterfox", "--with-app-name=posterfox",
                "--with-unsigned-addon-scopes=app,system", "mk_add_options MOZ_TELEMETRY_REPORTING=0",
                "mk_add_options MOZ_DATA_REPORTING=0", "--disable-crashreporter", "--disable-updater",
                "--disable-lto", "--disable-debug-symbols", "MOZ_PARALLEL_BUILD=4"):
        assert opt in sh, opt
    assert subprocess.run(["bash", "-n", str(ROOT / "tools/portable-build.sh")]).returncode == 0
    # mach must be allowed to fetch the bootstrap's own Python packages (taskcluster): "none" stops configure.
    assert "MACH_BUILD_PYTHON_NATIVE_PACKAGE_SOURCE=pip" in sh and "MACH_BUILD_PYTHON_NATIVE_PACKAGE_SOURCE=none" not in sh.replace("NOT Gentoo's MACH_BUILD_PYTHON_NATIVE_PACKAGE_SOURCE=none", "")
    rel = (ROOT / "tools/portable-release.sh").read_text()
    assert subprocess.run(["bash", "-n", str(ROOT / "tools/portable-release.sh")]).returncode == 0
    assert "smoke.py" in rel and "RELEASE CHECK FAILED -- nothing published" in rel
    assert "userdel pfbuild" in rel and "MOZBUILD_STATE_PATH=$P/.mozbuild" in rel   # nothing left in the VM's image
