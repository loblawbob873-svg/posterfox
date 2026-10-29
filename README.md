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
  and closing the tab deletes its data. Saved passwords are kept.
- **PosterChan AI in the AI sidebar.** Firefox's own AI panel opens your PosterChan instance's AI chat. "Summarize
  this page" and the other prompts land in the box for you to read and send.
- **Your Firefox profile carries over.** Passwords, bookmarks and history stay where Firefox keeps them.

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

PosterFox is not affiliated with or endorsed by Mozilla. Firefox is a trademark of the Mozilla Foundation.

Maintainers: [docs/MAINTAINING.md](docs/MAINTAINING.md).
