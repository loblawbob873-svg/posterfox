/* A BROWSER IDENTITY PER TAB ("we need to randomly change the user agent for each tab to real browsers (chrome,
 * firefox, brave, etc)", 2026-10-29).
 *
 * Every tab is already its own container, so the identity is the container's, chosen when it is made and kept for its
 * life: one page sees ONE browser, whatever it asks. A User-Agent header that says Chrome under a navigator.userAgent
 * that says Firefox is more identifying than either alone, so the header (onBeforeSendHeaders) and the page's
 * navigator (a content script registered FOR THAT CONTAINER, so it runs before any page script) always agree.
 *
 * Only real browsers, at versions that exist: derived from this Firefox's own version, so they move with every
 * PosterFox update and never age into a fingerprint. Chrome, Edge and Brave ship one major behind Firefox (Brave sends
 * Chrome's string exactly); Safari's major is its September release. Tor tabs all get the SAME identity (Firefox on
 * Windows, as Tor Browser presents): among Tor users, looking like every other one is the point.
 *
 * Pure part first (node-tested); the browser part is `install`. */
var PFAgent = (function () {
  const WIN = 'Windows NT 10.0; Win64; x64', MAC = 'Macintosh; Intel Mac OS X 10_15_7', LINUX = 'X11; Linux x86_64';
  function versions(ffMajor, now) {
    const ff = Number(ffMajor) || 140, d = now || new Date();
    const safari = d.getUTCFullYear() - (d.getUTCMonth() >= 8 ? 1999 : 2000);
    return { ff, chrome: ff - 1, safari };
  }
  function profiles(v) {
    const chrome = os => `Mozilla/5.0 (${os}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${v.chrome}.0.0.0 Safari/537.36`;
    const firefox = os => `Mozilla/5.0 (${os}; rv:${v.ff}.0) Gecko/20100101 Firefox/${v.ff}.0`;
    return [
      { id: 'chrome-win', ua: chrome(WIN), platform: 'Win32', vendor: 'Google Inc.' },
      { id: 'chrome-mac', ua: chrome(MAC), platform: 'MacIntel', vendor: 'Google Inc.' },
      { id: 'chrome-linux', ua: chrome(LINUX), platform: 'Linux x86_64', vendor: 'Google Inc.' },
      { id: 'edge-win', ua: chrome(WIN) + ` Edg/${v.chrome}.0.0.0`, platform: 'Win32', vendor: 'Google Inc.' },
      { id: 'brave-win', ua: chrome(WIN), platform: 'Win32', vendor: 'Google Inc.' },
      { id: 'firefox-win', ua: firefox(WIN), platform: 'Win32', vendor: '' },
      { id: 'firefox-mac', ua: firefox(MAC), platform: 'MacIntel', vendor: '' },
      { id: 'firefox-linux', ua: firefox(LINUX), platform: 'Linux x86_64', vendor: '' },
      { id: 'safari-mac', ua: `Mozilla/5.0 (${MAC}) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/${v.safari}.0 Safari/605.1.15`,
        platform: 'MacIntel', vendor: 'Apple Computer, Inc.' },
    ].map(p => Object.assign(p, { appVersion: p.ua.slice('Mozilla/'.length) }));
  }
  const TOR_ID = 'firefox-win';
  function pick(list, isTor, rand) {
    if (isTor) return list.find(p => p.id === TOR_ID);
    return list[Math.floor((rand === undefined ? Math.random() : rand) * list.length) % list.length];
  }
  /* What runs in the page before its own scripts: navigator's four answers, defined on the page's own object. The
   * profile goes in as JSON (never spliced as text), and only these keys. */
  function pageCode(p) {
    const data = JSON.stringify({ userAgent: p.ua, appVersion: p.appVersion, platform: p.platform, vendor: p.vendor });
    return `(function(){try{const v=${data},w=window.wrappedJSObject,n=w.navigator;` +
      `for(const k of Object.keys(v)){Object.defineProperty(n,k,{get:exportFunction(function(){return v[k];},window),configurable:true});}` +
      `}catch(e){}})();`;
  }

  // ---- the browser ----
  function install(isTorStore) {
    const ff = (/Firefox\/(\d+)/.exec(navigator.userAgent) || [])[1];
    const list = profiles(versions(ff));
    const byStore = new Map();    // cookieStoreId -> { profile, script }
    async function assign(store, isTor) {
      if (byStore.has(store)) return byStore.get(store).profile;
      const profile = pick(list, isTor);
      const entry = { profile, script: null };
      byStore.set(store, entry);
      try {
        entry.script = await browser.contentScripts.register({ matches: ['<all_urls>'], js: [{ code: pageCode(profile) }],
          runAt: 'document_start', allFrames: true, matchAboutBlank: true, cookieStoreId: store });
      } catch (_) { /* an older Firefox: the header alone */ }
      return profile;
    }
    function release(store) {
      const e = byStore.get(store); if (!e) return;
      byStore.delete(store);
      try { if (e.script) e.script.unregister(); } catch (_) { }
    }
    browser.webRequest.onBeforeSendHeaders.addListener(details => {
      const e = byStore.get(details.cookieStoreId); if (!e) return {};
      const headers = (details.requestHeaders || []).filter(h => h.name.toLowerCase() !== 'user-agent');
      headers.push({ name: 'User-Agent', value: e.profile.ua });
      return { requestHeaders: headers };
    }, { urls: ['<all_urls>'] }, ['blocking', 'requestHeaders']);
    return { assign, release, of: store => (byStore.get(store) || {}).profile || null };
  }
  return { versions, profiles, pick, pageCode, install, TOR_ID };
})();
if (typeof module !== 'undefined') module.exports = PFAgent;
