/* PosterFox: every tab its own container. The decisions, kept free of the browser API so tests/ can run them.
 *
 * A tab in the DEFAULT store ("firefox-default") is not allowed to load a web page: the page is cancelled and reopened
 * in a fresh temporary container, in the same place in the tab strip, and the default-store tab is closed. A blank
 * new tab is moved the same way. A container belongs to exactly one tab and is removed -- and with it every cookie
 * and every byte of site storage -- when that tab closes. Containers this add-on made are recognised by name, so the
 * ones a crash left behind are swept at the next start. */
var PFContainers = (function () {
  const DEFAULT = 'firefox-default';
  const NAME = 'PosterFox tab';
  const COLORS = ['blue', 'turquoise', 'green', 'yellow', 'orange', 'red', 'pink', 'purple'];
  /** Pages that never need a container of their own: the browser's own pages and add-on pages. */
  function isInternal(url) {
    return !url || /^(about:|moz-extension:|chrome:|resource:|view-source:|data:|blob:|javascript:)/i.test(url);
  }
  /** Should this request be moved into a new container? */
  function shouldMove(details, tab) {
    if (!tab || details.type !== 'main_frame' || details.tabId < 0) return false;
    if (tab.incognito || tab.cookieStoreId !== DEFAULT) return false;
    return !isInternal(details.url);
  }
  /** Should this tab -- a NEW-TAB PAGE, finished loading -- be moved into a container of its own?
   *
   * Only the new-tab page itself (about:newtab / about:home), never `about:blank`. Every tab Firefox opens for a page
   * starts as about:blank and may even report it finished before it navigates: Settings (about:preferences) and an
   * add-on's own page (uBlock's dashboard, a moz-extension: page) did exactly that, and moving the tab replaced the page
   * with an empty container tab ("ublock dashboard is not opening in posterfox, It just opens in a new container tab",
   * "firefox settings also does not open up", 2026-10-29). A tab that goes on to load a web page is moved by the
   * request handler with its address; one that stays about:blank holds nothing to isolate. */
  function shouldMoveNewTab(tab) {
    if (!tab || tab.incognito || tab.cookieStoreId !== DEFAULT || tab.status === 'loading') return false;
    const u = tab.url || '';
    return u === 'about:newtab' || u === 'about:home';
  }
  /** A default-store tab that may still turn out to be a new-tab page (or a page that loaded before this add-on could
   *  see its request): judged once it has finished loading. */
  function mightBeNew(tab) {
    if (!tab || tab.incognito || tab.cookieStoreId !== DEFAULT) return false;
    const u = tab.url || '';
    return u === 'about:newtab' || u === 'about:home' || u === 'about:blank' || u === '';
  }
  /** A tab that already SHOWS a web page in the default store -- one that loaded before this add-on was running (the
   *  first tab of a browser started with a link). It is reopened in a container of its own, at its address; file:,
   *  data: and the browser's own pages cannot be reopened by an add-on and stay where they are. */
  function shouldReopen(tab) {
    if (!tab || tab.incognito || tab.cookieStoreId !== DEFAULT) return false;
    return /^(https?|ftp):/i.test(tab.url || '');
  }
  /** How long the start-up sweep lets the first tabs settle before judging them (see background.js). */
  const SETTLE_MS = 1500;
  function colorFor(n) { return COLORS[n % COLORS.length]; }
  return { DEFAULT, NAME, SETTLE_MS, isInternal, shouldMove, shouldMoveNewTab, mightBeNew, shouldReopen, colorFor };
})();
if (typeof module !== 'undefined') module.exports = PFContainers;
