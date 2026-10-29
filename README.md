# PosterFox

**Firefox for PosterChanOS.** It is Mozilla's Firefox, built from Mozilla's source with as few changes as possible:

- **PosterFox branding**, and a window that looks like the rest of the PosterChan desktop: the cyberpunk theme, neon
  edges and the same window controls.
- **No telemetry, compiled out.** It isn't merely switched off; the reporting code isn't in the build.
- **uBlock Origin** and **Privacy Badger** built in.
- **Private by default.** No history is kept, everything (cookies, site data, cache, downloads, sessions) is cleared
  when PosterFox closes, and **every tab is its own container**: a login in one tab is invisible to every other tab,
  and closing the tab deletes its data. Saved passwords are kept.
- **PosterChan AI in the AI sidebar.** Firefox's own AI panel opens your PosterChan instance's AI chat. "Summarize
  this page" and the other prompts land in the box for you to read and send.
- **Your Firefox profile carries over.** Passwords, bookmarks and history stay where Firefox keeps them.

Coming next: **PosterChan Connect**, a built-in add-on for PosterChan password autofill, bookmark sync over Nostr,
and a switch that sends the browser through PosterChanOS's Tor.

PosterFox is not affiliated with or endorsed by Mozilla. Firefox is a trademark of the Mozilla Foundation.

Maintainers: [docs/MAINTAINING.md](docs/MAINTAINING.md).
