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
  /** Should this freshly created tab (blank / new tab page) be moved? */
  function shouldMoveNewTab(tab) {
    if (!tab || tab.incognito || tab.cookieStoreId !== DEFAULT) return false;
    const u = tab.url || '';
    return u === 'about:newtab' || u === 'about:home' || u === 'about:blank' || u === '';
  }
  function colorFor(n) { return COLORS[n % COLORS.length]; }
  return { DEFAULT, NAME, isInternal, shouldMove, shouldMoveNewTab, colorFor };
})();
if (typeof module !== 'undefined') module.exports = PFContainers;
