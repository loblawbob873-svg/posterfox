/* PosterFox: tabs you have not looked at for two minutes go to sleep ("can you automatically put tabs to sleep after
 * 2min ?", 2026-10-29). Firefox's own discard: the tab stays in the strip with its title, icon and container, frees its
 * memory and CPU, and loads again when it is clicked. The decision is kept free of the browser API so tests/ can run it.
 *
 * Never put to sleep: the tab in front, a tab still loading, one making sound (music, a call), one using the camera,
 * microphone or screen, and a pinned tab (mail, chat -- the ones that are pinned to keep running). */
var PFTabSleep = (function () {
  const AFTER_MS = 2 * 60 * 1000;
  const EVERY_MS = 20 * 1000;
  function shouldSleep(tab, now) {
    if (!tab || tab.active || tab.discarded || tab.pinned || tab.audible) return false;
    if (tab.status && tab.status !== 'complete') return false;
    const s = tab.sharingState || {};
    if (s.camera || s.microphone || s.screen) return false;
    if (/^about:(blank|newtab|home)$/.test(tab.url || '')) return false;     // nothing to free
    return typeof tab.lastAccessed === 'number' && now - tab.lastAccessed >= AFTER_MS;
  }
  return { AFTER_MS, EVERY_MS, shouldSleep };
})();
if (typeof module !== 'undefined') module.exports = PFTabSleep;
if (typeof browser !== 'undefined' && browser.tabs && browser.tabs.discard) {
  setInterval(async () => {
    const now = Date.now();
    for (const t of await browser.tabs.query({})) {
      if (PFTabSleep.shouldSleep(t, now)) browser.tabs.discard(t.id).catch(() => {});
    }
  }, PFTabSleep.EVERY_MS);
}
