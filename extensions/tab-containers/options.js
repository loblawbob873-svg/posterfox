/* The always-in-Tor list (tor.js siteOf / background.js): add, remove, and see what an administrator preset. */
(async function () {
  const list = document.getElementById('list'), input = document.getElementById('site');
  async function draw() {
    const own = (await browser.storage.local.get('torSites')).torSites || [];
    let preset = []; try { preset = (await browser.storage.managed.get('torSites')).torSites || []; } catch (_) { }
    list.textContent = '';
    if (!own.length && !preset.length) { const li = document.createElement('li'); li.className = 'empty'; li.textContent = 'No sites yet.'; list.append(li); }
    for (const d of preset.map(PFTor.siteOf).filter(Boolean)) {
      const li = document.createElement('li'); li.textContent = d;
      const s = document.createElement('span'); s.className = 'preset'; s.textContent = 'set by your administrator'; li.append(s); list.append(li);
    }
    for (const d of own) {
      const li = document.createElement('li'); li.textContent = d;
      const b = document.createElement('button'); b.textContent = 'Remove';
      b.onclick = async () => { await browser.storage.local.set({ torSites: own.filter(x => x !== d) }); draw(); };
      li.append(b); list.append(li);
    }
  }
  document.getElementById('add').onsubmit = async (e) => {
    e.preventDefault();
    const d = PFTor.siteOf(input.value);
    if (!d) { input.setCustomValidity('Not a site name or address'); input.reportValidity(); return; }
    input.setCustomValidity('');
    const own = (await browser.storage.local.get('torSites')).torSites || [];
    if (!own.includes(d)) await browser.storage.local.set({ torSites: own.concat(d) });
    input.value = ''; draw();
  };
  draw();
})();
