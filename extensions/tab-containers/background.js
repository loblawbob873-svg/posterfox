/* PosterFox Tab Containers: the browser half. See containers.js for the rules. */
(function () {
  const C = PFContainers;
  const ours = new Set();          // cookieStoreIds this add-on created (one per tab)
  const moving = new Set();        // default-store tabs being replaced (so they are not handled twice)
  let n = 0;

  const tor = new Set();            // the ones that are Tor tabs (tor.js): their requests go through Tor
  const agent = PFAgent.install();  // each container's browser identity (useragent.js)
  async function fresh(isTor) {
    const id = await browser.contextualIdentities.create(isTor
      ? { name: PFTor.NAME + ' ' + (++n), color: 'purple', icon: 'fingerprint' }
      : { name: C.NAME + ' ' + (++n), color: C.colorFor(n), icon: 'circle' });
    ours.add(id.cookieStoreId);
    if (isTor) tor.add(id.cookieStoreId);
    await agent.assign(id.cookieStoreId, isTor);   // before the tab opens: its first request already carries it
    return id.cookieStoreId;
  }

  // ---- Tor tabs (tor.js) ----
  // A Tor container made anywhere (another window of this profile, the release check) is a Tor container here too.
  if (browser.contextualIdentities.onCreated) browser.contextualIdentities.onCreated.addListener(info => {
    const c = info && info.contextualIdentity;
    if (c && PFTor.isTorName(c.name)) { ours.add(c.cookieStoreId); tor.add(c.cookieStoreId); agent.assign(c.cookieStoreId, true); }
  });
  if (browser.proxy && browser.proxy.onRequest)
    browser.proxy.onRequest.addListener(details => PFTor.route(details, tor), { urls: ['<all_urls>'] });
  async function openTor(url, from) {
    const store = await fresh(true);
    const opts = { cookieStoreId: store, active: true };
    if (from) { opts.index = from.index + 1; opts.windowId = from.windowId; }
    if (PFTor.openable(url)) opts.url = url;
    return browser.tabs.create(opts);
  }
  let torSaid = 0;
  if (browser.proxy && browser.proxy.onError) browser.proxy.onError.addListener(() => {
    // A Tor tab whose Tor is not running fails -- by design -- and says why, at most once a minute.
    if (!tor.size || Date.now() - torSaid < 60000 || !browser.notifications) return;
    torSaid = Date.now();
    browser.notifications.create('pf-tor', { type: 'basic', title: 'Tor is not running',
      message: 'The Tor tab could not connect. Turn Tor on (on PosterChanOS: the Tor switch in the tray), then reload. Nothing was sent without it.' }).catch(() => {});
  });
  if (browser.menus) {
    browser.menus.create({ id: 'pf-tor-new', title: 'New Tor tab', contexts: ['tab'] });
    browser.menus.create({ id: 'pf-tor-link', title: 'Open link in a Tor tab', contexts: ['link'] });
    browser.menus.onClicked.addListener((info, tab) => {
      if (info.menuItemId === 'pf-tor-new') openTor('', tab);
      else if (info.menuItemId === 'pf-tor-link') openTor(info.linkUrl, tab);
    });
  }
  if (browser.commands) browser.commands.onCommand.addListener(async (c) => {
    if (c !== 'new-tor-tab') return;
    const [cur] = await browser.tabs.query({ active: true, currentWindow: true });
    openTor('', cur);
  });
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
    if (!C.mightBeNew(tab)) return;
    if (C.shouldMoveNewTab(tab)) { replace(tab, ''); return; }
    waiting.add(tab.id);                         // about:blank, or still loading: judged when it finishes (below)
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
      if (!used.has(store)) { ours.delete(store); tor.delete(store); agent.release(store); browser.contextualIdentities.remove(store).catch(() => {}); }
    }
  });

  // Containers a crash left behind (no tab uses them) are swept at start; live ones are adopted.
  (async () => {
    const [ids, tabs] = await Promise.all([browser.contextualIdentities.query({}), browser.tabs.query({})]);
    const used = new Set(tabs.map(t => t.cookieStoreId));
    for (const id of ids) {
      const isTor = PFTor.isTorName(id.name);
      if (!isTor && !id.name.startsWith(C.NAME + ' ')) continue;
      const base = isTor ? PFTor.NAME : C.NAME;
      if (used.has(id.cookieStoreId)) { ours.add(id.cookieStoreId); if (isTor) tor.add(id.cookieStoreId); agent.assign(id.cookieStoreId, isTor);
        n = Math.max(n, parseInt(id.name.slice(base.length + 1), 10) || 0); }
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
