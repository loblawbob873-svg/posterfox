# PosterChan Connect (phase 2): passwords, bookmark sync and Tor, inside PosterFox

A built-in add-on in PosterFox's application scope (unsigned, updated with the browser). It never holds a key: every
secret stays in the PosterChan desktop, which is where the person's Nostr signer and the decrypted vault live.

## The bridge

```
PosterFox add-on --(native messaging, stdin/stdout JSON)--> posterchan-connect (small host, /usr/lib/posterfox/)
   --(unix socket $XDG_RUNTIME_DIR/posterchan-connect.sock, owner-only 0600)--> PosterChan desktop (Electron main)
   --(IPC)--> the client page (PCVault, bookmarks doc, Tor state)
```

- The socket follows `desktop/opener.js` (`posterchan-open.sock`): it lives in the user's runtime dir, is mode 0600,
  and checks the peer's uid (SO_PEERCRED), so another account on the same machine cannot ask.
- The native-messaging manifest (`/usr/lib64/mozilla/native-messaging-hosts/posterchan_connect.json`) allows ONLY
  the Connect add-on's id.
- If the desktop isn't running, the host answers `{"ok":false,"why":"PosterChan is not running"}`. The add-on says
  so, and never falls back to anything.

## Passwords

- `vault.match(origin)` returns the vault entries for that exact origin: usernames only, never passwords.
- `vault.fill(id, origin)` returns one password. The desktop shows a consent prompt the first time a site asks
  ("PosterFox wants your login for github.com: Allow once / Always for this site / Deny"). "Always" is remembered in
  the vault's own (encrypted) settings, not in the browser.
- Saving a new login offers "Save to PosterChan Passwords". The client writes it through PCVault's own save path,
  with the same home-relay write gate every private document uses.
- Firefox's own password manager is turned off by default (`signon.rememberSignons=false` as a default) so the person
  is not asked twice.

## Bookmark sync

- One encrypted document per account, `pcai:browser-bookmarks` (NIP-44 to the account's own key, kind 30078). It holds
  the tree as `{id, parent, title, url, pos, ts, deleted}` records.
- The add-on keeps a mapping of Firefox's bookmark ids to these record ids. Every change (bookmarks API events) becomes
  a record edit, and a pull applies other devices' records to the tree. Last writer wins **per record**, never per
  document. Deletions are tombstones, so a device that was offline cannot resurrect what another device deleted.
- The same rules as Folder Sync: a read that did not come back is never "no bookmarks"; a pull that would delete more
  than half of the tree is refused and reported.
- PosterChan's own Bookmarks screen (saved posts) is a different thing and stays separate.

## Tor switch

- A toolbar button and its state: Direct / Through Tor.
- "Through Tor" sets the browser's proxy (`browser.proxy.settings`) to SOCKS5 `127.0.0.1:9050` with remote DNS, which
  is PosterChanOS's system Tor (gentoo.sh configures `SocksPort 9050`). The desktop app's own Tor uses ephemeral
  ports, so Connect asks the desktop over the bridge which port to use when the system service isn't there.
- The button turns magenta while browsing through Tor, and a check against the Tor Project's check service confirms
  it.

## Tests owed with it

- The host, run with a fake desktop socket: the manifest's allowed id, a peer of another uid refused, "not running".
- The add-on, under Firefox's own test harness or a headless PosterFox: fill, the consent prompt, a pull that would
  delete half the tree being refused, Tor on/off as seen by the proxy settings.
