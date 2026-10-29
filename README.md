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

Coming next: **Tor tabs** through PosterChanOS's Tor.

PosterFox is not affiliated with or endorsed by Mozilla. Firefox is a trademark of the Mozilla Foundation.

Maintainers: [docs/MAINTAINING.md](docs/MAINTAINING.md).
