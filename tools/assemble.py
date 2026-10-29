#!/usr/bin/env python3
"""Collect everything PosterFox adds to Firefox into build/files-posterfox (the ebuild's files/posterfox/).

    tools/assemble.py --posterchanai ~/posterchanai

  branding/      browser/branding/posterfox overlay: strings, prefs, configure.sh + images drawn by make-branding.py
  distribution/  policies.json, distribution.ini, default prefs, the autoconfig hook + posterfox.cfg, window chrome
  extensions/    posterchan-cyberpunk.xpi, built UNSIGNED from posterchanai/os/firefox-theme (app scope allows it)

Deterministic, so rebuilding unchanged sources gives the same files (and the ebuild's revision only moves when
something really changed).
"""
import argparse
import importlib.util
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "tools"))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _xpi(src: pathlib.Path, out: pathlib.Path):
    """Zip an add-on directory deterministically (fixed order and timestamps: same sources, same bytes)."""
    import zipfile
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(p for p in src.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(str(f.relative_to(src)), (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, f.read_bytes())


def assemble(posterchanai: pathlib.Path, out: pathlib.Path = None) -> pathlib.Path:
    out = out or HERE / "build" / "files-posterfox"
    if out.exists():
        shutil.rmtree(out)
    b = out / "branding"
    shutil.copytree(HERE / "branding", b, ignore=shutil.ignore_patterns("src"))
    _load(HERE / "tools" / "make-branding.py", "make_branding").write(b)
    shutil.copytree(HERE / "distribution", out / "distribution")
    theme = posterchanai / "os" / "firefox-theme"
    if not (theme / "build.py").exists():
        raise SystemExit(f"no theme sources at {theme} -- pass --posterchanai <checkout>")
    built = _load(theme / "build.py", "theme_build").build(str(out / "_theme"))
    (out / "extensions").mkdir()
    shutil.move(built, out / "extensions" / "posterchan-cyberpunk.xpi")
    _xpi(HERE / "extensions" / "tab-containers", out / "extensions" / "posterfox-tab-containers.xpi")
    shutil.rmtree(out / "_theme", ignore_errors=True)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--posterchanai", type=pathlib.Path, default=pathlib.Path.home() / "posterchanai")
    a = ap.parse_args(argv)
    print(assemble(a.posterchanai))


if __name__ == "__main__":
    main()
