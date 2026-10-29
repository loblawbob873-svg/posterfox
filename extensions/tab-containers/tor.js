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
  return { NAME, PROXIES, isTorName, route, openable };
})();
if (typeof module !== 'undefined') module.exports = PFTor;
