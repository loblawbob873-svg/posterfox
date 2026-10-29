/* PosterFox: TOR TABS ("yes, build the Tor tabs too", 2026-10-29). A Tor tab is a container of its own, and every request
 * made in it -- DNS included -- goes through the Tor running on this machine (SOCKS 9050, PosterChanOS's own; 9150, Tor
 * Browser's, as the failover). Every other tab is left exactly as it was.
 *
 * FAILS CLOSED: when Tor is not running, the request fails. Nothing in this list says "direct", and posterfox-prefs.js
 * turns off Firefox's own fall-back-to-direct (network.proxy.failover_direct), so a Tor tab never quietly loads over the
 * ordinary connection. WebRTC in a page loaded through a proxy is held to that proxy
 * (media.peerconnection.ice.proxy_only_if_behind_proxy). This hides the address; it is not Tor Browser's fingerprinting
 * protection, and the tab says nothing to the contrary.
 *
 * The decisions are here, free of the browser API, so tests/ can run them; background.js makes the containers. */
var PFTor = (function () {
  const NAME = 'PosterFox Tor tab';
  const PROXIES = [
    { type: 'socks', host: '127.0.0.1', port: 9050, proxyDNS: true, failoverTimeout: 3 },
    { type: 'socks', host: '127.0.0.1', port: 9150, proxyDNS: true },
  ];
  function isTorName(name) { return typeof name === 'string' && name.startsWith(NAME + ' '); }
  /** The proxy for one request: Tor's for a Tor tab's request, nothing (Firefox's own setting) for any other. */
  function route(details, torStores) {
    return details && details.cookieStoreId && torStores.has(details.cookieStoreId) ? PROXIES : undefined;
  }
  /** Only web addresses are opened in a Tor tab; the browser's own pages have nothing to hide and cannot be. */
  function openable(url) { return /^(https?|ftp):/i.test(String(url || '')); }
  /* SITES THAT ALWAYS OPEN IN TOR ("should open .onions in tor automatically and should be able to set a list of sites
   * to use on Tor only somehow in an easy way", 2026-10-29). A .onion can only be reached through Tor, so it always is;
   * a listed site is matched with every subdomain (example.com covers www.example.com, not notexample.com). */
  function hostOf(url) { try { return new URL(String(url || '')).hostname.toLowerCase().replace(/\.$/, ''); } catch (_) { return ''; } }
  /** What goes on the list for an address or a typed name: its host, without a leading www. '' when it is not one. */
  function siteOf(input) {
    let s = String(input || '').trim().toLowerCase();
    if (!s) return '';
    if (!/^[a-z][a-z0-9+.-]*:/.test(s)) s = 'https://' + s;
    const h = hostOf(s);
    return /^[a-z0-9-]+(\.[a-z0-9-]+)+$/.test(h) ? h.replace(/^www\./, '') : '';
  }
  function onList(url, sites) {
    const h = hostOf(url);
    return !!h && (sites || []).some(d => d && (h === d || h.endsWith('.' + d)));
  }
  /** Does this address belong in a Tor tab? A web address that is a .onion or on the list. */
  function wantsTor(url, sites) {
    if (!openable(url)) return false;
    const h = hostOf(url);
    return h.endsWith('.onion') || onList(url, sites);
  }
  return { NAME, PROXIES, isTorName, route, openable, hostOf, siteOf, onList, wantsTor };
})();
if (typeof module !== 'undefined') module.exports = PFTor;
