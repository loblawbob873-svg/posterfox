# Maintaining PosterFox

PosterFox is Firefox for PosterChanOS. It is built from **Mozilla's own source, the way Gentoo builds it**, plus a
short list of PosterChan changes. There is no fork of Firefox's source code and no patch queue to rebase. Every
PosterFox change is one of two things:

- a **file this repository adds**: branding, prefs, policies, add-ons, the window stylesheet;
- one of about twenty **exact edits to Gentoo's own Firefox ebuild**, made by `tools/make-ebuild.py`.

That is what keeps it cheap to maintain. Gentoo's Firefox maintainers do the hard work for every Mozilla release
(new toolchains, patches, build flags). PosterFox regenerates itself from their ebuild, and if they change a line we
depend on, the generator stops and names it.

**Normally there is nothing to do.** A daily timer checks for a new Firefox, and if there is one it builds, signs
and publishes PosterFox by itself. This document is for when you want to change something, or when that timer
stopped and told you why.

---

## 1. What PosterFox changes

| What | Where | How |
|---|---|---|
| Name, icons, About dialog | `branding/` | Mozilla's rebranding hook, `--with-branding=browser/branding/posterfox`. Mozilla's `unofficial` branding is copied first, then ours is laid over it. Images are drawn by `tools/make-branding.py`. |
| Binary `posterfox`, app name PosterFox | generator | `--with-app-name=posterfox --with-app-basename=PosterFox` |
| Profiles stay in `~/.mozilla/firefox` | generator | `imply_option("MOZ_APP_PROFILE", "mozilla/firefox")` is appended to `browser/moz.configure` at prepare. Configure **refuses** this value from a mozconfig. Moving from firefox-bin keeps passwords and bookmarks. |
| **No telemetry, compiled out** | generator | The `telemetry` USE flag is removed and every `use telemetry` reads false. The result is `MOZ_TELEMETRY_REPORTING=0`, `MOZ_DATA_REPORTING=0`, `MOZ_SERVICES_HEALTHREPORT=0` and `MOZ_CRASHREPORTER=0`, plus Gentoo's telemetry prefs. |
| **Private by default** | `distribution/policies.json`, `distribution/posterfox-prefs.js` | No history and no form history. `SanitizeOnShutdown` clears cookies, site data, cache, downloads, sessions and site settings on exit. Saved passwords are kept. This is **not** permanent private browsing, because containers do not work in private browsing. |
| **Every tab its own container** | `extensions/tab-containers/` | A built-in add-on. A page loading in a tab is reopened in a fresh container in the same place, and the container is deleted (cookies and storage too) when its tab closes. Containers the person makes are never touched. |
| **Tabs sleep after 2 minutes** | `extensions/tab-containers/tabsleep.js` | Firefox's own `tabs.discard` for a tab not looked at for two minutes. Never the tab in front, one making sound, one using the camera, microphone or screen, a pinned tab or one still loading. |
| uBlock Origin, Privacy Badger, PosterChan Passwords | `pins.json`, `distribution/policies.json` | AMO-signed releases fetched by `SRC_URI` (pinned versions, Manifest-hashed) and force-installed by policy. |
| Cyberpunk theme | `posterchanai/os/firefox-theme` | Built **unsigned** into the application scope (`browser/extensions/`). This build allows that (`--with-unsigned-addon-scopes=app,system`). It is the default theme. |
| **Looks like a PosterChan window** | `distribution/posterfox-chrome.css` | Uses the desktop's own values: the title bar (tab strip) in `--panel2`, the theme's violet toolbar, and the selected tab in the focused-window neon ring. The stylesheet carries the theme's colours itself, so the look does not depend on the theme add-on loading. It is registered by the autoconfig and scoped to `browser.xhtml`, never to web pages. |
| Window buttons like PosterChan windows | `distribution/xdg/gtk-3.0/settings.ini` | `gtk-decoration-layout=:minimize,maximize,close`. The `posterfox` launcher puts that folder first in `XDG_CONFIG_DIRS`. GTK's default layout gives Firefox a close button only. The person's own `~/.config/gtk-3.0` still wins. |
| AI sidebar → PosterChan AI | `distribution/posterfox.cfg` | The autoconfig reads `~/.config/posterchan-desktop/config.json` (`instance`) and sets `browser.ml.chat.provider` to `<instance>/client?pcai=1`. The client puts Firefox's `q=` prompt into AI chat, unsent. Only a plain `https?://host[:port]` origin is accepted. |
| Quiet defaults | `distribution/policies.json`, `posterfox-prefs.js` | No studies, Pocket, sponsored tiles, onboarding, default-browser nagging or self-update (Portage updates it). |
| Stable-system dependencies | `pins.json` → `bundled_libs` | `system-*` USE flags turned off when the system library is still `~amd64` in PosterChanOS's tree. Firefox's bundled copy is used instead (`system-av1` for 159). |
| Icon | `branding/src/` | PosterChan riding a purple ostrich (Nostr's). See §6. |

Prefs and policies are **defaults**, not locks: anyone can change them in PosterFox's own settings.

**A file at `/etc/posterfox/policies/policies.json` REPLACES ours.** Firefox reads the system policy file first and
then ignores the bundled one (it does not merge them). Leave that path empty unless you mean to replace every
PosterFox policy.

---

## 2. The normal case: the timer does it

`tools/release.sh` runs daily on server1, at 07:30 from a user timer. That is after nas.lan's Gentoo mirror sync
(06:00), so whatever Gentoo changed this morning is seen the same day. Each run:

1. **Decides what should be published.** That is the newest Firefox in the build VM's synced Gentoo tree, at this
   repository's `REVISION`, giving `posterfox-<PV>-r<REV>`. If the binhost already serves exactly that, **and** it was
   linked against the libraries Gentoo's binhost serves today, the run stops: nothing to do.

   The second half matters. A binary records the exact library versions it was built for (icu, ffmpeg, libvpx,
   dav1d...). When Gentoo moves one of them, every machine's next system update installs the new library and then
   **refuses our binary and compiles Firefox from source**. `tools/stale_deps.py` compares the published build with
   Gentoo's binhost index. If anything moved, the run rebuilds the same version as a new build of it, and machines
   pick that up.
2. **Regenerates the overlay package** in the posterchanai checkout. Tests run first, then the overlay's own checks.
   It commits the package and **deploys** it with `sync.sh` like any other change, which publishes the overlay.
3. **Builds on the build VM.** First it updates PosterFox's libraries on the VM to what Gentoo's binhost serves
   (binaries only). `--buildpkgonly` links against what the VM has installed, so without this a new build could be
   stale on the day it is published. Then `emerge --oneshot --buildpkgonly`. The compile takes about 18 minutes on the
   VM's own cores (see "distcc" below).
4. **Checks the built browser** before anyone gets it. `tools/smoke.py` unpacks the built package on the VM and starts
   it headless as an ordinary user, then asks it over Marionette (Firefox's own remote protocol):
   - its name is PosterFox, telemetry is compiled out and off, and Mozilla accounts are disabled;
   - the enterprise policies are active;
   - uBlock Origin, Privacy Badger, PosterChan Passwords, the tab-container add-on and the cyberpunk theme are enabled;
   - history and form history are off, and data is cleared on exit;
   - the PosterChan window stylesheet is registered;
   - H.264, AAC, VP9, AV1, Opus, FLAC and MP3 can play;
   - every new tab opens in its own container.

   Any failure stops the run. "It compiled" is not "it works": r6 and r7 compiled and could not even be installed.
5. **Signs** the package on server1 (the key never leaves it), rebuilds the binhost index, publishes it to nas, and
   confirms the public index lists the new package. An unsigned package is never published.

It stops at the first failure with **nothing half-published**. It also refuses to start while another deploy is
running. A run with nothing to do takes about a minute; a release takes the deploy gate (~30 min) plus the build
(1–2 h).

Look at what it did:

```
tail -50 ~/.cache/posterfox/release.log
systemctl --user status posterfox-release.timer posterfox-release.service
curl -s https://gentoo.poster.place/posterchan-binpkgs/Packages | grep -A3 'CPV: www-client/posterfox'
tools/release.sh --dry-run          # what would it do right now?
```

Turning the timer on (once):

```
cp tools/posterfox-release.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now posterfox-release.timer
```

---

## 3. Recipes

### The timer stopped: what each message means

The last `STOPPED:` line in `~/.cache/posterfox/release.log` names the step.

| Message | Cause | Fix |
|---|---|---|
| `edit '<name>': expected 1 occurrence(s) …` (in the log, from update.sh) | Gentoo changed a line in their Firefox ebuild that one of our edits depends on. | Open `tools/make-ebuild.py`, find the named edit in `transform()` and the matching line in the new Gentoo ebuild (`/var/db/repos/gentoo/www-client/firefox/` on the VM), and adjust that one substitution. Run `pytest tests`, commit, run `release.sh`. **Never edit the generated ebuild by hand**: the next update overwrites it. |
| `the build failed on the VM` with `… have been masked … ~amd64 keyword` | The new Firefox wants a system library that PosterChanOS's stable tree does not have yet. | Find the flag (`emerge -pv --oneshot www-client/posterfox` on the VM says `required by …[system-xyz]`), add it to `bundled_libs` in `pins.json`, bump `REVISION`, commit, run `release.sh`. |
| `the build failed on the VM` (anything else) | A compile error. | The log has the tail. The full log is `/var/tmp-build/portage/www-client/posterfox-*/temp/build.log` on the VM (cleaned on success). Usually Gentoo has already fixed it in a newer ebuild revision; wait a day and the timer picks it up. |
| `the overlay checks refused the new ebuild` | One of posterchanai's overlay tests failed on the generated package. | Run them in posterchanai (`tests/test_overlay_*.py`, `test_code_git_ui_and_os.py`, `test_gentoo_packages_exist.py`) and fix what they say. |
| `the deploy did not pass` | posterchanai's deploy gate failed. | Not a PosterFox problem as a rule. It is whatever the gate says, often a flaky test under load. Fix or re-run the deploy; the next `release.sh` continues from where the overlay is. |
| `posterchanai has uncommitted changes` | Someone is working in `~/posterchanai`. | Commit or stash; the next run proceeds. |
| `signing failed` / `no signature` | The key is missing or `gpkg-sign` failed. | `GNUPGHOME=~/.config/posterfox/gnupg gpg --list-secret-keys`. Never make a new key unless the old one is truly lost: machines trust its fingerprint. |
| `… does not list … yet` | router.lan serves the binhost over NFS and briefly caches the old directory. | Wait a minute and run `release.sh` again; it will say "already serves". |

### Change something in PosterFox (the look, a pref, a policy, an add-on)

1. Edit it. Use the table in §1 to find where it lives.
2. For the look, preview it **without building PosterFox**:
   `tools/preview-chrome.sh /tmp/look.png https://example.org`. This runs a stock Firefox in a headless Wayfire with
   PosterFox's stylesheet and takes a screenshot. It shows the stylesheet alone, not the theme add-on or the window
   buttons.
3. Run the tests: `python3 -m pytest tests` (the project venv has pytest: `~/posterchanai/venv-unified/bin/python`).
4. Bump `REVISION` by one. It becomes the ebuild's `-rN`, and machines only update when it moves.
5. Commit, then push to **both** remotes: `git push origin main` (Nostr) and `git push github main`. In practice the
   Nostr push mirrors to GitHub too, because GitHub is a clone URL in the repo announcement.
6. Run `tools/release.sh`, or let the timer do it.

### Bump uBlock Origin, Privacy Badger or PosterChan Passwords

- **uBlock Origin:** `pins.json` → `ublock_origin` = the release tag on
  https://github.com/gorhill/uBlock/releases.
- **Privacy Badger:** `pins.json` → `privacy_badger` and `privacy_badger_amo_file` = `current_version.version` and
  the file id in `current_version.file.url` from
  `https://addons.mozilla.org/api/v5/addons/addon/privacy-badger17/`.
- **PosterChan Passwords:** `pins.json` → `posterchan_passwords` and `posterchan_passwords_amo_file` from
  `https://addons.mozilla.org/api/v5/addons/addon/posterchan-passwords/` (posterchanai's CI publishes each version there
  when `extension/manifest.json`'s version changes). Between PosterFox releases AMO updates it in place anyway.
- Then bump `REVISION` and run `release.sh`. The Manifest is written from what was downloaded: compare
  `sha256sum ~/.cache/posterfox/distfiles/posterfox-privacybadger-*.xpi` with the `hash` AMO lists.

### Change the icon

`branding/src/posterfox-1024.png` is the full scene, used at 48 px and up. `posterfox-small-1024.png` is the
close-up, used at 16–32 px, where a whole scene turns to mud. Both are 1024×1024 on the round neon badge. Replace
either, then follow the same steps as above (tests, `REVISION`, commit, release). Every size is redrawn from them.
See §6 for how the current one was made.

### Release by hand

```
tools/release.sh --dry-run      # what it would do
tools/release.sh                # do it (the same thing the timer runs)
```

### A bad release went out

Machines never downgrade by themselves. So **fix forward**: revert the change in this repository, bump `REVISION`,
and run `release.sh`. The new, higher revision is what `emerge -u` installs. Do not delete a published package from
the binhost while machines may still be fetching it; the next release replaces it in the index.

---

## 4. How the pieces fit

```
posterfox repo (this)                    posterchanai repo
  branding/ distribution/ extensions/      os/overlay/www-client/posterfox/   <- GENERATED here by update.sh
  tools/make-ebuild.py  ------------------>  posterfox-<PV>-r<REV>.ebuild + files/ + Manifest
                                            sync.sh deploy -> publish_overlay.sh
                                                    |
                                    https://gentoo.poster.place/posterchan-overlay.git
                                                    |
build VM (PosterChanOS, on nas.lan)  <--------------+   emaint sync -r posterchan
  emerge --buildpkgonly  (its own cores; ~18 min)  ->  tools/smoke.py checks the built browser
        |  posterfox-…gpkg.tar
        v
server1: gpkg-sign (key in ~/.config/posterfox/gnupg) -> emaint binhost --fix -> rsync
        |
https://gentoo.poster.place/posterchan-binpkgs/    (nas: /raid/distfiles/distfiles/posterchan-binpkgs)
        |
PosterChanOS machines  (gentoo.sh: binrepos entry + the public key)   <-- NOT YET, see §7
```

**Repositories.**
- This repo lives at `nostr://npub1fdtthaq…/relay.poster.place/posterfox` (origin; its clone URL is
  `https://poster.place/git/npub1fdtthaq…/posterfox.git`), mirrored at
  `https://github.com/loblawbob873-svg/posterfox`.
- The repo's kind-30617 announcement lists both. It was published with a script because `ngit init` could not
  connect to either relay.

**The build VM** is the libvirt VM "PosterChan" on nas.lan (`ssh -J nas.lan root@192.168.122.32`), the same one
that builds the PosterChanOS ISOs. It is a PosterChanOS install, so a package built there matches installed
machines: the same profile, USE flags, CHOST and `-march=x86-64-v3`. Its PosterFox settings:

- **Nothing else.** The VM's disk becomes the ISO, so it holds no PosterFox build configuration at all: `release.sh`
  passes `PORTAGE_TMPDIR=/var/tmp-build` and `MAKEOPTS` on its own `emerge` line, deletes the build tree and the browser
  check's `posterfoxtest` account when it is done, and `gentoo.sh livecd` excludes `/var/tmp-build`. (A package.env
  entry and a distcc host list naming this LAN were found inside the 2026-10-29 ISO before it was published; both were
  removed and the ISO rebuilt.) `/etc/portage/package.accept_keywords/posterfox` stays: every PosterChanOS machine
  has it.

**distcc is not used.** Measured 2026-10-29: Firefox's build calls clang by its absolute path, which bypasses Portage's
distcc wrapper, so no work left the VM. The compile takes about 18 minutes on the VM's own cores. distcc was removed
from the VM, and nas.lan's `posterfox-vm.conf` distccd drop-in was deleted (it applies at distccd's next restart).

**The signing key** was made once by `tools/binhost-setup.sh`.
- Fingerprint `7B690AA70C09AD1AD7748CF5B6F8DA9DDF2EF936`; the public half is `keys/posterchanos-binpkgs.asc`.
- Signing: `gpkg-sign --allow-unsigned`, because gpkg-sign first verifies the package and a fresh build has no
  signature yet. `BINPKG_GPG_SIGNING_BASE_COMMAND` is overridden so its lock is `~/.config/posterfox/gnupg/.sign.lock`;
  Portage's default lock is in `/run/lock`, which only root can write.
- The secret half is only in `~/.config/posterfox/gnupg` on server1. It has no passphrase so the timer can sign
  unattended, which is exactly why it signs nothing but PosterChanOS packages and never goes anywhere else
  (not GitHub, not a CI secret).

**The binhost** is `/raid/distfiles/distfiles/posterchan-binpkgs` on nas.lan, served by router.lan as
`https://gentoo.poster.place/posterchan-binpkgs/`. nas mirrors Gentoo's distfiles into `/raid/distfiles` with
`rsync --delete` every morning. That job excludes this directory (`/opt/admintools/admintools/servers.py`, commit
`da4d260`), exactly as it excludes the overlay. **Any new directory in that tree needs the same exclusion**, or it
is deleted every day at 06:00. Publishing never uses `--delete` either: a lost stage directory on server1 must not
empty the binhost.

**Machines** get PosterFox updates from `update-posterchan`, which runs `emerge -u --usepkgonly` for it on every update.
If there is no newer binary yet, it keeps the installed browser; it never compiles it.

---

## 5. Things that will bite you

- **The build VM's disk becomes the ISO.** Only ever `emerge --buildpkgonly` PosterFox there; a plain emerge
  installs it into the next ISO. `release.sh` also deletes `/var/tmp-build/portage/www-client/posterfox-*` after a
  build, because that 40 GB must not reach an image. After a failed manual build, delete it yourself.
- **Generate from the VM's Gentoo tree, never from the machine you are on.** server1's tree was two weeks behind
  `gentoo.poster.place` on 2026-10-28. A PosterFox generated from a newer tree than the machines have cannot be
  installed by them. `release.sh` and `update.sh --gentoo-ssh` take the tree from the VM.
- **`MOZ_APP_PROFILE` from a mozconfig fails configure** ("can not be set by mozconfig. Values are accepted from:
  implied"). That is why it is implied in `browser/moz.configure`.
- **`pkill -f <pattern>` over ssh can kill your own ssh session** when the pattern is part of the command you sent
  (exit 255, nothing done). Use `pkill -x <name>`.
- **`diff` is aliased to nvim on server1.** Use `/usr/bin/diff`.
- **The chrome preview on server1 runs through Xwayland.** server1's GTK is built `-wayland`. The preview cannot
  show the theme add-on (a theme sideloaded into a fresh profile does not activate) or the window buttons (there is
  no window manager in it), so check those on a real PosterChanOS desktop.
- **Stock Firefox will not load an unsigned add-on.** The tab-containers add-on can only be tried in PosterFox
  itself (application scope) or temporarily via `about:debugging`.
- **Containers and private browsing do not mix.** "Never remember history" in Firefox's settings is permanent
  private browsing and switches containers off. PosterFox gets the same effect from prefs plus `SanitizeOnShutdown`
  instead.
- **Firefox's own updater is off** (`DisableAppUpdate`). Portage is the updater. A PosterFox that offers "Restart to
  update" means a policy did not load.

---

## 6. The icon

PosterChan riding a purple ostrich (Nostr's ostrich), on a round night-navy badge with the cyan-to-magenta
PosterChan rim. How it was made:

1. The drawing came from this node's own image model as `branding/src/posterfox-art-source.png`. The prompt was
   chibi PosterChan in her black hoodie with the yellow star and the cat-ear hood, riding a bright violet ostrich,
   sticker style, plain white background; seed 44.
2. It was cut out by **flood-filling the near-white background from the edges**. An AI background remover was tried
   first and cut the ostrich's head off.
3. It was placed on the badge with a white sticker outline, in Python.

At 16–32 px only her face in the cat hood is used.

---

## 7. Not done yet

Done since the first release (2026-10-29):
- **PosterChanOS installs PosterFox.** `gentoo.sh` adds the `[posterchan]` binhost with `verify-signature = true`,
  trusts the key pinned in it (`POSTERCHAN_BINPKG_FPR`), and installs PosterFox from its signed binary in its own step
  (`installBrowser`, `gentoo.sh browser`); links open in it. Verified on the build VM: it installs from the binhost,
  and a package signed by another key is refused.
- **The daily timer is enabled** on server1 (`systemctl --user list-timers posterfox-release.timer`).

Still open:
- **Machines installed before the switch** keep `firefox-bin` until somebody runs `gentoo.sh repo` then
  `gentoo.sh browser` on them. They are not migrated automatically.
- **PosterChan Connect** (passwords from the PosterChan vault, bookmark sync over Nostr, a Tor switch) is designed
  in `docs/CONNECT.md` and not built.

Update this section as each lands.

---

## 8. Repository layout

```
branding/                  brand strings, prefs, configure.sh; branding/src = the icon masters + art source
distribution/              policies.json, distribution.ini, posterfox-prefs.js, autoconfig.js + posterfox.cfg,
                           posterfox-chrome.css, xdg/gtk-3.0/settings.ini
extensions/tab-containers/ the every-tab-its-own-container add-on (rules in containers.js, browser glue in background.js)
keys/                      the binary-package signing key, PUBLIC half + fingerprint
pins.json                  uBlock Origin / Privacy Badger versions, bundled_libs
REVISION                   PosterFox's own revision (the ebuild's -rN)
tools/
  make-ebuild.py           Gentoo's firefox ebuild -> www-client/posterfox (the asserted edits) + the launcher
  make-branding.py         every icon and logo at Mozilla's sizes, deterministically
  assemble.py              collects everything into build/files-posterfox (the ebuild's files/posterfox/)
  update.sh                regenerate the overlay package (--check: is there a newer Firefox?)
  release.sh               the whole release, start to finish (what the timer runs)
  binhost-setup.sh         one time: the signing key + the binhost directory
  preview-chrome.sh        screenshot the window chrome without building
  posterfox-release.{service,timer}
tests/                     the generator against a real Gentoo ebuild and a broken one, the launcher, branding,
                           policies, the autoconfig under node, the tab-containers add-on against a fake browser
docs/CONNECT.md            PosterChan Connect design (phase 2)
```
