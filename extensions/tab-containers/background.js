/* PosterFox Tab Containers: the browser half. See containers.js for the rules. */
(function () {
  const C = PFContainers;
  const ours = new Set();          // cookieStoreIds this add-on created (one per tab)
  const moving = new Set();        // default-store tabs being replaced (so they are not handled twice)
  let n = 0;

  async function fresh() {
    const id = await browser.contextualIdentities.create({ name: C.NAME + ' ' + (++n), color: C.colorFor(n), icon: 'circle' });
    ours.add(id.cookieStoreId);
    return id.cookieStoreId;
  }
  async function replace(tab, url) {
    if (moving.has(tab.id)) return;
    moving.add(tab.id);
    try {
      const store = await fresh();
      const opts = { cookieStoreId: store, index: tab.index, active: tab.active, windowId: tab.windowId };
      if (url && !C.isInternal(url)) opts.url = url;
      if (tab.openerTabId != null) opts.openerTabId = tab.openerTabId;
      await browser.tabs.create(opts);
      await browser.tabs.remove(tab.id);
    } finally { moving.delete(tab.id); }
  }

  browser.webRequest.onBeforeRequest.addListener(details => {
    return browser.tabs.get(details.tabId).then(tab => {
      if (!C.shouldMove(details, tab)) return {};
      replace(tab, details.url);
      return { cancel: true };
    }, () => ({}));
  }, { urls: ['<all_urls>'], types: ['main_frame'] }, ['blocking']);

  /* A TAB IS JUDGED BLANK ONLY ONCE IT HAS FINISHED LOADING BLANK. A tab still loading reads `about:blank` whatever it
   * is about to show -- the first tab of a browser started with a link (`posterfox https://...`, which is how every link
   * from the desktop arrives), a tab opened by a link from another app -- and moving it then replaced the page with an
   * empty tab: the link was lost. So it waits: a web page it goes on to load is moved by the request handler above,
   * WITH its address; a page that request handler never sees (file:, data:) stays where it is, in the default store,
   * because an add-on cannot open those addresses itself and losing the page is worse than sharing a store for it. */
  const waiting = new Set();
  function consider(tab) {
    if (!C.shouldMoveNewTab(tab)) return;
    if (tab.status === 'loading') { waiting.add(tab.id); return; }
    replace(tab, '');
  }
  browser.tabs.onCreated.addListener(consider);
  browser.tabs.onUpdated.addListener((id, info, tab) => {
    if (!waiting.has(id) || info.status !== 'complete') return;
    waiting.delete(id);
    if (C.shouldMoveNewTab(tab)) replace(tab, '');
    else if (C.shouldReopen(tab)) replace(tab, tab.url);   // it loaded before the request handler could move it
  });

  // A container lives exactly as long as its tab: closing the tab deletes its cookies and storage.
  browser.tabs.onRemoved.addListener(async (gone) => {
    waiting.delete(gone);
    const tabs = await browser.tabs.query({});
    const used = new Set(tabs.map(t => t.cookieStoreId));
    for (const store of [...ours]) {
      if (!used.has(store)) { ours.delete(store); browser.contextualIdentities.remove(store).catch(() => {}); }
    }
  });

  // Containers a crash left behind (no tab uses them) are swept at start; live ones are adopted.
  (async () => {
    const [ids, tabs] = await Promise.all([browser.contextualIdentities.query({}), browser.tabs.query({})]);
    const used = new Set(tabs.map(t => t.cookieStoreId));
    for (const id of ids) {
      if (!id.name.startsWith(C.NAME + ' ')) continue;
      if (used.has(id.cookieStoreId)) { ours.add(id.cookieStoreId); n = Math.max(n, parseInt(id.name.slice(C.NAME.length + 1), 10) || 0); }
      else browser.contextualIdentities.remove(id.cookieStoreId).catch(() => {});
    }
    /* THE START-UP TABS ARE JUDGED AFTER THEY SETTLE. Measured on the build VM: at the moment this ran, the first tab of
     * `posterfox <link>` was still a finished blank page about to start loading the link -- moving it made an empty
     * container tab and could not remove the original (it was busy loading), so the browser came up with the link in the
     * DEFAULT store AND a spare empty tab beside it. Re-read after a moment: blank -> a container tab; a web page that
     * loaded before this add-on ran -> reopened at its address in a container; anything else stays. */
    setTimeout(async () => {
      for (const t of await browser.tabs.query({})) {
        if (C.shouldReopen(t)) replace(t, t.url); else consider(t);
      }
    }, C.SETTLE_MS);
  })();
})();
