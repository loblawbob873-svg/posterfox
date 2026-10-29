# Maintaining PosterFox

PosterFox is Firefox, built from Mozilla's own source the way Gentoo builds it, with a short list of changes on top.
It has no fork of Firefox's source and no patch queue. Keeping it that way is what keeps maintenance cheap: every
PosterFox change is either a file this repository adds, or one of a dozen exact edits to Gentoo's own Firefox ebuild.

## What PosterFox changes

| Change | Where | How |
|---|---|---|
| Name, icons, About dialog | `branding/` | `--with-branding=browser/branding/posterfox` (Mozilla's supported rebranding hook; `unofficial` is copied first, then ours is laid over it) |
| Binary `posterfox`, app name `PosterFox` | ebuild | `--with-app-name=posterfox --with-app-basename=PosterFox` |
| Profiles stay in `~/.mozilla/firefox` | ebuild | `MOZ_APP_PROFILE=mozilla/firefox`, so moving from firefox-bin keeps passwords, bookmarks and history |
| **No telemetry, compiled out** | ebuild | The `telemetry` USE flag is removed and every `use telemetry` reads false: `MOZ_TELEMETRY_REPORTING=0`, `MOZ_DATA_REPORTING=0`, `MOZ_SERVICES_HEALTHREPORT=0`, `MOZ_CRASHREPORTER=0`, plus Gentoo's telemetry prefs |
| uBlock Origin | `pins.json`, `distribution/policies.json` | The AMO-signed release from GitHub (`SRC_URI`), force-installed by policy |
| Cyberpunk theme | `posterchanai/os/firefox-theme` | Built unsigned into the **application scope** (`browser/extensions/`), which this build allows (`--with-unsigned-addon-scopes=app,system`), and made the default theme |
| AI sidebar → PosterChan AI | `distribution/posterfox.cfg` | Autoconfig reads `~/.config/posterchan-desktop/config.json` and sets `browser.ml.chat.provider` to `<instance>/client?pcai=1`; the client puts Firefox's `q=` prompt into AI chat, unsent |
| Window looks like a PosterChan window | `distribution/posterfox-chrome.css` | Registered by the autoconfig as a stylesheet scoped to `browser.xhtml` (never to web pages) |
| Quiet defaults | `distribution/policies.json`, `posterfox-prefs.js` | No studies, Pocket, sponsored tiles, onboarding or default-browser nagging. These are DEFAULTS: the person can change them |

**A file at `/etc/posterfox/policies/policies.json` REPLACES ours.** Firefox reads the system policy file first and
ignores the bundled one (it does not merge them). Leave that path empty unless you mean to.

## Updating to a new Firefox (the usual job)

Gentoo packages every Mozilla release within days, so PosterFox follows Gentoo's tree:

```
VM="-J nas.lan root@192.168.122.32"
tools/update.sh --gentoo-ssh "$VM" --check           # exit 10 = a newer Firefox is available
tools/update.sh --gentoo-ssh "$VM" --posterchanai ~/posterchanai
```

**Generate from the build VM's tree, never from whatever machine you are on.** The ebuild's dependencies must exist
in the Gentoo snapshot PosterChanOS machines sync (gentoo.poster.place). server1's own tree was two weeks behind it on
2026-10-28, and a PosterFox generated from a NEWER tree than the machines have cannot be installed by them.

**PosterChanOS is a stable system.** A new Firefox often wants a library that is still `~amd64` (159.0 wanted
libaom-3.14.1 for `system-av1`). Add that flag to `bundled_libs` in `pins.json`, so Firefox's bundled copy is used,
and regenerate. `emerge -pv --oneshot www-client/posterfox` on the build VM finds them.

`update.sh` runs the tests, regenerates `os/overlay/www-client/posterfox/` in the posterchanai checkout from the newest
`firefox-*.ebuild`, and writes the Manifest (downloading the Firefox source, Gentoo's patchset and uBlock Origin into
`~/.cache/posterfox/distfiles`). Then commit the overlay in posterchanai and build (below).

**When it stops with `edit '...': expected 1 occurrence(s)`**, Gentoo changed a line one of our edits depends on.
Open `tools/make-ebuild.py`, look at the named edit and the new Gentoo ebuild, and adjust that one substitution.
Every edit is listed in `transform()`. Never edit the generated ebuild by hand: the next update overwrites it.

uBlock Origin: bump `pins.json` (`ublock_origin`) to a new release tag, then run `update.sh`.

A change to PosterFox itself (branding, prefs, policies, the chrome CSS) bumps `REVISION`, which becomes the
ebuild's `-rN`, so installed machines pick it up on their next `emerge -u`.

## Building the binary package

PosterChanOS machines should not compile Firefox. That takes hours and tens of GB of build space. Build it once on
the **PosterChanOS build VM** (the libvirt VM "PosterChan" on nas.lan, which also builds the ISOs). It is itself a
PosterChanOS install, so the binary package matches what installed machines run: the same profile, USE flags and
CHOST.

```
ssh -J nas.lan root@192.168.122.32
update-posterchan                         # the overlay with the new posterfox ebuild
echo 'www-client/posterfox ~amd64' > /etc/portage/package.accept_keywords/posterfox
FEATURES="distcc buildpkg" PORTAGE_TMPDIR=/var/tmp/posterfox-build \
  emerge --oneshot --buildpkg www-client/posterfox
```

distcc spreads the C/C++ compiles over server1, router.lan and nas.lan (their `/etc/distcc/hosts`). Rust is most of
Firefox and does not distribute, so plan on a long build either way. `PORTAGE_TMPDIR` must have about 40 GB free and
be on disk: a Firefox build does not fit in a RAM tmpfs.

The result is `/var/cache/binpkgs/www-client/posterfox/posterfox-<ver>-r<rev>-1.gpkg.tar`.

## Publishing

The binary packages are served from the PosterChan binhost, signed. Installed machines verify the signature before
installing anything. `gentoo.sh` configures that repository and installs `www-client/posterfox` with
`--getbinpkgonly`. If no matching binary is published, it installs `www-client/firefox-bin` instead: a PosterChanOS
install never waits hours for a browser to compile.

## The icon

PosterChan riding a purple ostrich (Nostr's ostrich), on a round night-navy badge with the cyan-to-magenta PosterChan
rim. `branding/src/posterfox-1024.png` is the full scene (48 px and up); `posterfox-small-1024.png` is her face in
the cat hood, for 16-32 px, where a whole scene turns to mud. The drawing came from this node's own image model
(`posterfox-art-source.png`, seed 44), cut out of its white background by flood fill from the edges (an
AI background remover cut the ostrich's head off), and badged in Python. Replace either master and run
`tools/update.sh`: every size is redrawn from them.

## Repository layout

```
branding/          brand strings, prefs, configure.sh; images are DRAWN by tools/make-branding.py from branding/src
distribution/      policies.json, distribution.ini, posterfox-prefs.js, autoconfig.js, posterfox.cfg, posterfox-chrome.css
pins.json          versions of third-party add-ons (uBlock Origin)
REVISION           PosterFox's own revision (the ebuild's -rN)
tools/
  make-ebuild.py   Gentoo firefox ebuild -> www-client/posterfox (the asserted edits)
  make-branding.py the icons and logos, at Mozilla's sizes, deterministically
  assemble.py      collects everything into build/files-posterfox (the ebuild's files/posterfox/)
  update.sh        the whole update, start to finish
tests/             the generator against a real Gentoo ebuild, a broken one, the autoconfig under node, ...
```
