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

  browser.tabs.onCreated.addListener(tab => { if (C.shouldMoveNewTab(tab)) replace(tab, ''); });

  // A container lives exactly as long as its tab: closing the tab deletes its cookies and storage.
  browser.tabs.onRemoved.addListener(async () => {
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
    for (const t of tabs) if (C.shouldMoveNewTab(t)) replace(t, '');
  })();
})();
