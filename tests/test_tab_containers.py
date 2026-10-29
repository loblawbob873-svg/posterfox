"""PosterFox Tab Containers: every tab its own container, deleted with the tab.

The shipped containers.js + background.js, run under node against a fake `browser` (tabs, contextualIdentities,
webRequest) that keeps real state, so what is asserted is what happens to tabs and containers.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXT = ROOT / "extensions" / "tab-containers"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node")

HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const state = { tabs: SEED_TABS, ids: SEED_IDS, nextTab: 100, nextId: 1, removedIds: [] };
const L = { req: null, created: null, removed: null, updated: null };
// A tab finishes loading: its address is now `url`, as the browser reports it.
const finish = async (id, url) => { const t = state.tabs.find(t => t.id === id); if (!t) return; t.url = url; t.status = 'complete';
                                    if (L.updated) L.updated(id, { status: 'complete' }, t); };
const browser = {
  contextualIdentities: {
    create: async o => { const id = { ...o, cookieStoreId: 'firefox-container-' + (state.nextId++) }; state.ids.push(id); return id; },
    remove: async s => { state.ids = state.ids.filter(i => i.cookieStoreId !== s); state.removedIds.push(s); },
    query: async () => state.ids.slice(),
  },
  tabs: {
    get: async id => { const t = state.tabs.find(t => t.id === id); if (!t) throw new Error('no tab'); return t; },
    query: async () => state.tabs.slice(),
    create: async o => { const t = { id: state.nextTab++, url: o.url || 'about:newtab', cookieStoreId: o.cookieStoreId || 'firefox-default',
                                     index: o.index || 0, active: !!o.active, windowId: 1, incognito: false, status: o.status };
                         state.tabs.push(t); if (L.created) L.created(t); return t; },
    onUpdated: { addListener: f => { L.updated = f; } },
    remove: async id => { state.tabs = state.tabs.filter(t => t.id !== id); if (L.removed) await L.removed(id); },
    onCreated: { addListener: f => { L.created = f; } },
    onRemoved: { addListener: f => { L.removed = f; } },
  },
  webRequest: { onBeforeRequest: { addListener: f => { L.req = f; } } },
};
const ctx = vm.createContext({ browser, console, Set, Promise, parseInt, setTimeout });
vm.runInContext(fs.readFileSync(EXT + '/containers.js', 'utf8') + '\n' + fs.readFileSync(EXT + '/background.js', 'utf8'), ctx);
const tick = () => new Promise(r => setTimeout(r, 20));
(async () => {
  await tick();
  const out = {};
  STEPS
  console.log(JSON.stringify({ out, tabs: state.tabs, ids: state.ids.map(i => i.cookieStoreId), removed: state.removedIds }));
})();
"""


def run(seed_tabs, seed_ids, steps):
    js = (HARNESS.replace("SEED_TABS", json.dumps(seed_tabs)).replace("SEED_IDS", json.dumps(seed_ids))
          .replace("EXT", json.dumps(str(EXT))).replace("STEPS", steps))
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def tab(i, url, store="firefox-default", index=0, incognito=False):
    return {"id": i, "url": url, "cookieStoreId": store, "index": index, "active": True, "windowId": 1, "incognito": incognito}


def test_a_page_in_the_default_store_reopens_in_its_own_container_in_the_same_place():
    r = run([tab(1, "about:blank", "firefox-container-9", 0), tab(2, "https://example.org", index=1)],
            [{"cookieStoreId": "firefox-container-9", "name": "Personal"}], """
      out.verdict = await L.req({ type: 'main_frame', tabId: 2, url: 'https://example.org/' });
      await tick();""")
    assert r["out"]["verdict"] == {"cancel": True}
    moved = [t for t in r["tabs"] if t["url"] == "https://example.org/"]
    assert len(moved) == 1 and moved[0]["cookieStoreId"].startswith("firefox-container-") and moved[0]["index"] == 1
    assert not any(t["id"] == 2 for t in r["tabs"]), "the default-store tab was left behind"


def test_two_tabs_get_two_different_containers():
    r = run([tab(1, "https://a.example"), tab(2, "https://b.example", index=1)], [], """
      await L.req({ type: 'main_frame', tabId: 1, url: 'https://a.example/' }); await tick();
      await L.req({ type: 'main_frame', tabId: 2, url: 'https://b.example/' }); await tick();""")
    stores = {t["cookieStoreId"] for t in r["tabs"]}
    assert len(stores) == 2 and "firefox-default" not in stores, r["tabs"]


def test_a_blank_new_tab_moves_too():
    r = run([], [], """
      const t = await browser.tabs.create({}); await tick();""")
    assert len(r["tabs"]) == 1 and r["tabs"][0]["cookieStoreId"] != "firefox-default", r["tabs"]


def test_closing_a_tab_deletes_its_container():
    r = run([tab(1, "https://a.example")], [], """
      await L.req({ type: 'main_frame', tabId: 1, url: 'https://a.example/' }); await tick();
      const t = (await browser.tabs.query({}))[0];
      await browser.tabs.remove(t.id); await tick();""")
    assert r["tabs"] == [] and r["ids"] == [], r
    assert len(r["removed"]) == 1


@pytest.mark.parametrize("url", ["about:preferences", "moz-extension://x/page.html", "view-source:https://a.example"])
def test_browser_pages_are_left_alone(url):
    r = run([tab(1, url)], [], """
      out.verdict = await L.req({ type: 'main_frame', tabId: 1, url: %s }); await tick();""" % json.dumps(url))
    assert r["out"]["verdict"] == {} and r["tabs"][0]["cookieStoreId"] == "firefox-default"


def test_a_tab_already_in_a_container_is_left_alone():
    r = run([tab(1, "https://a.example", "firefox-container-5")], [{"cookieStoreId": "firefox-container-5", "name": "Work"}], """
      out.verdict = await L.req({ type: 'main_frame', tabId: 1, url: 'https://a.example/x' }); await tick();""")
    assert r["out"]["verdict"] == {} and len(r["tabs"]) == 1


def test_a_private_window_is_left_alone():
    r = run([tab(1, "https://a.example", incognito=True)], [], """
      out.verdict = await L.req({ type: 'main_frame', tabId: 1, url: 'https://a.example/' }); await tick();""")
    assert r["out"]["verdict"] == {}


def test_leftovers_from_a_crash_are_swept_and_live_ones_kept():
    r = run([tab(1, "https://a.example", "firefox-container-2")],
            [{"cookieStoreId": "firefox-container-1", "name": "PosterFox tab 7"},
             {"cookieStoreId": "firefox-container-2", "name": "PosterFox tab 8"},
             {"cookieStoreId": "firefox-container-3", "name": "Banking"}], "")
    assert r["ids"] == ["firefox-container-2", "firefox-container-3"], r["ids"]   # the person's own container stays


def test_the_xpi_is_built_and_installed_in_the_app_scope():
    import importlib.util
    spec = importlib.util.spec_from_file_location("me", ROOT / "tools" / "make-ebuild.py")
    me = importlib.util.module_from_spec(spec); spec.loader.exec_module(me)
    t = me.transform((ROOT / "tests" / "fixtures" / "firefox-159.0.ebuild").read_text(), 1)
    assert "posterfox-tab-containers.xpi\" tab-containers@posterfox.poster.place.xpi" in t
    m = json.loads((EXT / "manifest.json").read_text())
    assert m["browser_specific_settings"]["gecko"]["id"] == "tab-containers@posterfox.poster.place"


def test_a_link_that_loaded_before_the_add_on_ran_is_reopened_in_its_own_container():
    """Measured on the VM: `posterfox <link>` loaded the link in the DEFAULT store before the add-on was running, and
    the start-up sweep (judging the tab while it was still blank) added a spare empty tab beside it."""
    r = run([tab(1, "http://127.0.0.1:8765/", index=0)], [], """
      await new Promise(r => setTimeout(r, 1700));""")
    assert [t["url"] for t in r["tabs"]] == ["http://127.0.0.1:8765/"], ("lost, duplicated or a spare tab", r["tabs"])
    assert r["tabs"][0]["cookieStoreId"] != "firefox-default", r["tabs"]


def test_the_first_tab_is_judged_after_it_settles_not_while_it_is_still_blank():
    r = run([tab(1, "about:blank")], [], """
      await tick(); out.early = (await browser.tabs.query({})).map(t => t.id);
      await finish(1, 'https://example.org/'); await new Promise(r => setTimeout(r, 1700));""")
    assert r["out"]["early"] == [1], "the first tab was replaced before it could start loading its link"
    assert [t["url"] for t in r["tabs"]] == ["https://example.org/"], r["tabs"]
    assert r["tabs"][0]["cookieStoreId"] != "firefox-default"


def test_a_browser_started_with_a_link_keeps_the_page_and_moves_it():
    """`posterfox https://...` (every link from the desktop): the first tab is still loading -- `about:blank` -- when
    the add-on starts. It used to be replaced by an EMPTY container tab and the link was lost (seen on the VM)."""
    r = run([dict(tab(1, "about:blank"), status="loading")], [], """
      await tick();
      out.verdict = await L.req({ type: 'main_frame', tabId: 1, url: 'https://example.org/' }); await tick();""")
    urls = [t["url"] for t in r["tabs"]]
    assert urls == ["https://example.org/"], ("the link was lost or a blank tab took its place", r["tabs"])
    assert r["tabs"][0]["cookieStoreId"] != "firefox-default"


def test_a_local_file_opened_from_the_desktop_stays_open():
    """An add-on cannot open file: (or data:) itself, so moving such a tab would lose the page: it stays put."""
    r = run([dict(tab(1, "about:blank"), status="loading")], [], """
      await tick(); await finish(1, 'file:///home/me/report.html'); await tick();""")
    assert [(t["id"], t["url"]) for t in r["tabs"]] == [(1, "file:///home/me/report.html")], r["tabs"]


def test_a_new_tab_that_finishes_blank_is_moved():
    r = run([], [], """
      const t = await browser.tabs.create({ status: 'loading', url: 'about:blank' }); await tick();
      out.waited = (await browser.tabs.query({})).length === 1 && (await browser.tabs.query({}))[0].cookieStoreId === 'firefox-default';
      await finish(t.id, 'about:newtab'); await tick();""")
    assert r["out"]["waited"], "a tab still loading was moved before it was known to be blank"
    assert len(r["tabs"]) == 1 and r["tabs"][0]["cookieStoreId"] != "firefox-default", r["tabs"]


@pytest.mark.parametrize("page", ["about:preferences", "moz-extension://ublock-id/dashboard.html", "about:addons"])
@pytest.mark.parametrize("reported", ["complete", "loading"])
def test_settings_and_add_on_pages_open_and_are_never_replaced_by_an_empty_tab(page, reported):
    """"ublock dashboard is not opening in posterfox, It just opens in a new container tab" and "firefox settings also
    does not open up ... just shows a new tab" (2026-10-29): the tab Firefox opens for them starts as about:blank -- and
    may say it has FINISHED as about:blank -- before it loads the page. That tab was replaced by an empty container tab."""
    r = run([], [], """
      const t = await browser.tabs.create({ status: %s, url: 'about:blank' }); await tick();
      await finish(t.id, %s); await new Promise(r => setTimeout(r, 1700));""" % (json.dumps(reported), json.dumps(page)))
    assert [t["url"] for t in r["tabs"]] == [page], ("the page was replaced, or a spare tab was opened", r["tabs"])
