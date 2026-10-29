#!/usr/bin/env python3
"""Has the published PosterFox binary been left behind by its libraries?

    tools/stale_deps.py --ours <binhost Packages> --gentoo <Gentoo binhost Packages> --cpv www-client/posterfox-159.0-r6

A binary package records the exact sub-slot of every library it was linked against (`dev-libs/icu:0/78.1=` in its
RDEPEND). When Gentoo moves one of those -- icu 78 -> 79, a new nss ABI -- a machine that updates its system gets the
new library from Gentoo's binhost, and Portage then REFUSES our PosterFox binary (it was built for the old one) and
compiles Firefox from source instead: hours, on somebody's laptop, from an ordinary `emerge -uDN @world`.

nas.lan mirrors the Gentoo tree and binhost every morning, so this is checked against what that mirror serves now.
Prints one atom per library that moved (the packages to update on the build VM before rebuilding), nothing when the
binary is current. Exit 0 either way; 2 when the question could not be answered (an unreadable index is never "fine").
"""
import argparse
import re
import sys
import urllib.request

# A resolved slot operator: [op]cat/pkg[-version]:SLOT/SUBSLOT=   (the only form a built package's RDEPEND carries)
_ATOM = re.compile(r"(?:^|\s)[<>=~!]*([A-Za-z0-9+_.-]+/[A-Za-z0-9+_-]+?)(?:-\d[^\s:\[]*)?:([^\s/=\[]+)/([^\s=\[]+)=")


def read(src):
    """Packages text from a path or an http(s) URL."""
    if re.match(r"https?://", src):
        with urllib.request.urlopen(src, timeout=60) as r:
            return r.read().decode("utf-8", "replace")
    with open(src, encoding="utf-8", errors="replace") as f:
        return f.read()


def blocks(text):
    """The package entries of a Packages index (the header block, which has no CPV, is skipped)."""
    out = []
    for chunk in re.split(r"\n\s*\n", text):
        d = {}
        for line in chunk.splitlines():
            k, sep, v = line.partition(": ")
            if sep:
                d[k] = v
        if "CPV" in d:
            out.append(d)
    return out


def _split_cpv(cpv):
    m = re.match(r"^([A-Za-z0-9+_.-]+/[A-Za-z0-9+_-]+?)-(\d.*)$", cpv)
    return (m.group(1), m.group(2)) if m else (cpv, "")


def _vkey(v):
    """A version sort key good enough to pick the newest of one package's builds (portage's vercmp when present)."""
    try:
        from functools import cmp_to_key
        from portage.versions import vercmp
        return cmp_to_key(lambda a, b: vercmp(a, b) or 0)(v)
    except Exception:
        parts = re.findall(r"\d+|[a-z]+", v)
        return [(0, int(p)) if p.isdigit() else (1, p) for p in parts]


def built_against(ours, cpv):
    """{cat/pkg: (slot, subslot)} for the newest build of `cpv` in our index; None if it is not there."""
    mine = [b for b in blocks(ours) if b.get("CPV") == cpv]
    if not mine:
        return None
    b = max(mine, key=lambda x: int(x.get("BUILD_ID", "0") or 0))
    return {m.group(1): (m.group(2), m.group(3)) for m in _ATOM.finditer(" " + b.get("RDEPEND", ""))}


def current(gentoo):
    """{(cat/pkg, slot): subslot of the newest version Gentoo's binhost serves in that slot}."""
    best = {}
    for b in blocks(gentoo):
        pn, ver = _split_cpv(b["CPV"])
        slot, _, sub = (b.get("SLOT") or "0").partition("/")
        key = (pn, slot)
        if key not in best or _vkey(ver) > _vkey(best[key][0]):
            best[key] = (ver, sub or slot)
    return {k: v[1] for k, v in best.items()}


def stale(ours, gentoo, cpv):
    """[(cat/pkg, built subslot, current subslot)]; raises LookupError when our package is not in our index."""
    deps = built_against(ours, cpv)
    if deps is None:
        raise LookupError(cpv + " is not in the binhost index")
    now = current(gentoo)
    out = []
    for pn, (slot, sub) in sorted(deps.items()):
        cur = now.get((pn, slot))
        # A library Gentoo's binhost does not carry (built from source everywhere) cannot be judged here; it is the
        # same on the build VM and on every machine, so it is not what strands a binary.
        if cur is not None and cur != sub:
            out.append((pn, sub, cur))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ours", required=True)
    ap.add_argument("--gentoo", required=True)
    ap.add_argument("--cpv", required=True)
    a = ap.parse_args(argv)
    try:
        moved = stale(read(a.ours), read(a.gentoo), a.cpv)
    except Exception as e:
        print("could not tell: %s" % e, file=sys.stderr)
        return 2
    for pn, was, now in moved:
        print(pn)
        print("  %s: built for %s, Gentoo now serves %s" % (pn, was, now), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
