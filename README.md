<p align="center"><img src="branding/src/posterfox-1024.png" alt="PosterFox: PosterChan riding a purple ostrich" width="280"></p>

# PosterFox

**Firefox for PosterChanOS.** It is Mozilla's Firefox, built from Mozilla's source with as few changes as possible:

- **PosterFox branding**, and a window that looks like the rest of the PosterChan desktop: the cyberpunk theme, neon
  edges and the same window controls.
- **No telemetry, compiled out.** It isn't merely switched off; the reporting code isn't in the build.
- **uBlock Origin**, **Privacy Badger** and **PosterChan Passwords** (passwords, bookmarks over Nostr, the NIP-07
  signer) built in. No Mozilla account and no Sync to Mozilla.
- **Tabs sleep** after two minutes in the background (never one playing sound or using the camera), so a hundred
  tabs cost what a few do.
- **Private by default.** No history is kept, everything (cookies, site data, cache, downloads, sessions) is cleared
  when PosterFox closes, and **every tab is its own container**: a login in one tab is invisible to every other tab,
  and closing the tab deletes its data. **Strict** tracking protection is on, and Firefox's own DNS over HTTPS is off.
- **PosterChan AI in the AI sidebar.** Firefox's own AI panel opens your PosterChan instance's AI chat. "Summarize
  this page" and the other prompts land in the box for you to read and send.
- **PosterChan Passwords, not Firefox's.** Firefox's password manager does not save or fill passwords (PosterChan
  Passwords does); logins an older Firefox profile holds stay readable in about:logins, to move over. Mozilla's own AI
  features are off too -- the AI sidebar is PosterChan's.
- **Your Firefox profile carries over.** Bookmarks and history stay where Firefox keeps them.
- **Tor tabs.** Right-click a tab → *New Tor tab*, right-click a link → *Open link in a Tor tab*, or Alt+Shift+T: a
  container whose every request (DNS too) goes through this machine's Tor (SOCKS 9050, or Tor Browser's 9150). With
  Tor off it fails, never falls back to a direct connection. It hides your address; it is not Tor Browser's
  anti-fingerprinting.
- **.onion addresses, and any site you choose, open in Tor by themselves.** Right-click a page → *Always open
  example.com in Tor* (its subdomains too); the list is in the Tab Containers add-on's settings, where sites can be
  added and removed. A link to one of them opened in an ordinary tab moves into a Tor tab in the same place.
- **Every tab presents a different real browser.** Each tab gets its own identity when it opens -- Chrome, Edge or
  Brave on Windows, macOS or Linux, Firefox, or Safari -- at current versions, and its requests and its pages see
  the same one. Tor tabs all look like Firefox on Windows, as Tor Browser does.

Everything above is a default, not a lock: it can be changed in Settings or about:config like any Firefox preference.

## Get PosterFox

- **PosterChanOS** ships it as the default browser, and `update-posterchan` keeps it current.
- **Gentoo**: signed binary packages (`www-client/posterfox`) from the PosterChanOS binhost,
  `https://gentoo.poster.place/posterchan-binpkgs`, with the `posterchan` overlay.
- **Any x86-64 Linux**: the portable tarball on the
  [releases page](https://github.com/loblawbob873-svg/posterfox/releases) -- unpack and run `posterfox/posterfox`.

## Source

PosterFox lives on Nostr (NIP-34), hosted by poster.place's git server; GitHub is a mirror of the same commits.

- **ngit / git over Nostr:** `nostr://npub1fdtthaqujtjcd6yfy7kt0zpkadyl9vvypq00s5nztnmche74d0tqv6uwwr/relay.poster.place/posterfox`
  (clone with `git-remote-nostr`, or browse it in any NIP-34 client)
- **HTTPS:** `https://poster.place/git/npub1fdtthaqujtjcd6yfy7kt0zpkadyl9vvypq00s5nztnmche74d0tqv6uwwr/posterfox.git`
- **On the web:** [poster.place/r/…/posterfox](https://poster.place/r/npub1fdtthaqujtjcd6yfy7kt0zpkadyl9vvypq00s5nztnmche74d0tqv6uwwr/posterfox)
  -- issues and patches welcome there.
- **Mirror:** [github.com/loblawbob873-svg/posterfox](https://github.com/loblawbob873-svg/posterfox)

PosterFox is not affiliated with or endorsed by Mozilla. Firefox is a trademark of the Mozilla Foundation.

Maintainers: [docs/MAINTAINING.md](docs/MAINTAINING.md).
