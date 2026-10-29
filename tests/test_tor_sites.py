"""PosterFox: .onion addresses and a list of sites always open in a Tor tab ("should open .onions in tor automatically and
should be able to set a list of sites to use on Tor only somehow in an easy way", 2026-10-29).

The shipped tor.js + background.js under node, against the fake `browser` of test_tab_containers.py (now with storage
and menus): what is asserted is which kind of container each page ends up in.
"""
import pathlib
import shutil
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_tab_containers import run, tab  # noqa: E402  (the shared fake browser)

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node")


def where(r):
    """For each open tab: its URL and whether its container is a Tor one."""
    return [(t["url"], t["cookieStoreId"] in r["torIds"]) for t in r["tabs"]]


def visit(url, **kw):
    return run([tab(1, "about:blank")], [], """
      out.verdict = await L.req({ type: 'main_frame', tabId: 1, url: %r }); await tick(); await tick();""" % url, **kw)


def test_an_onion_opens_in_a_tor_tab():
    r = visit("http://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion/")
    assert r["out"]["verdict"] == {"cancel": True}, "the .onion was loaded in the ordinary tab"
    assert where(r) == [("http://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion/", True)], where(r)


def test_a_listed_site_and_its_subdomains_open_in_tor_and_a_look_alike_does_not():
    assert where(visit("https://www.example.com/a", local={"torSites": ["example.com"]})) == [("https://www.example.com/a", True)]
    lookalike = where(visit("https://notexample.com/", local={"torSites": ["example.com"]}))
    assert lookalike and not lookalike[0][1], ("a different site was sent through Tor", lookalike)


def test_an_administrators_preset_counts_too():
    assert where(visit("https://leaks.example.org/", managed={"torSites": ["example.org"]})) == [("https://leaks.example.org/", True)]


def test_a_page_already_in_a_tor_tab_is_left_there():
    r = run([], [], """
      const t = await browser.tabs.create({ url: 'about:blank' }); await tick(); await tick();
      // make it a Tor tab first, via the menu
      const cur = (await browser.tabs.query({}))[0];
      await L.menuClick({ menuItemId: 'pf-tor-new' }, cur); await tick(); await tick();
      const torTab = (await browser.tabs.query({})).find(x => /firefox-container/.test(x.cookieStoreId) && x.id !== cur.id);
      out.count = (await browser.tabs.query({})).length;
      out.verdict = await L.req({ type: 'main_frame', tabId: torTab.id, url: 'http://abc.onion/' }); await tick();
      out.after = (await browser.tabs.query({})).length;""")
    assert r["out"]["verdict"] == {} and r["out"]["after"] == r["out"]["count"], r["out"]


def test_the_page_menu_adds_this_site_moves_the_tab_and_takes_it_back_off():
    r = run([tab(1, "https://news.example.net/story")], [], """
      await L.req({ type: 'main_frame', tabId: 1, url: 'https://news.example.net/story' }); await tick();
      let cur = (await browser.tabs.query({}))[0];
      await L.menuShown({ pageUrl: cur.url }, cur); out.offer = state.menus['pf-tor-site'].title;
      await L.menuClick({ menuItemId: 'pf-tor-site', pageUrl: cur.url }, cur); await tick(); await tick();
      cur = (await browser.tabs.query({}))[0];
      await L.menuShown({ pageUrl: cur.url }, cur); out.offerAfter = state.menus['pf-tor-site'].title;
      out.listed = state.local.torSites.slice();
      await L.menuClick({ menuItemId: 'pf-tor-site', pageUrl: cur.url }, cur); await tick();
      out.listedAfter = state.local.torSites.slice();""")
    assert r["out"]["offer"] == "Always open news.example.net in Tor", r["out"]
    assert r["out"]["listed"] == ["news.example.net"], r["out"]
    assert where(r) == [("https://news.example.net/story", True)], ("the tab did not move into Tor at once", where(r))
    assert r["out"]["offerAfter"].startswith("Stop always opening"), r["out"]
    assert r["out"]["listedAfter"] == [], r["out"]


def test_a_preset_site_cannot_be_removed_from_the_menu():
    r = run([tab(1, "https://a.example.org/")], [], """
      const cur = (await browser.tabs.query({}))[0];
      await L.menuShown({ pageUrl: 'https://a.example.org/' }, cur); out.m = state.menus['pf-tor-site'];""", managed={"torSites": ["example.org"]})
    assert r["out"]["m"]["enabled"] is False and "administrator" in r["out"]["m"]["title"], r["out"]


@pytest.mark.parametrize("given,want", [("https://WWW.Example.com/path?q=1", "example.com"), ("example.com", "example.com"),
                                        ("sub.example.co.uk", "sub.example.co.uk"), ("about:config", ""), ("not a site", ""), ("", "")])
def test_what_goes_on_the_list(given, want):
    import json, subprocess
    from test_tab_containers import EXT
    code = "global.window=global;eval(require('fs').readFileSync(%s,'utf8'));console.log(JSON.stringify(PFTor.siteOf(%s)))" % (
        json.dumps(str(EXT / "tor.js")), json.dumps(given))
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=20)
    assert json.loads(out.stdout) == want, (given, out.stdout, out.stderr)


def test_on_a_subdomain_the_menu_offers_to_stop_the_entry_that_covers_it():
    r = run([tab(1, "https://news.example.com/x")], [], """
      const cur = (await browser.tabs.query({}))[0];
      await L.menuShown({ pageUrl: 'https://news.example.com/x' }, cur); out.title = state.menus['pf-tor-site'].title;
      await L.menuClick({ menuItemId: 'pf-tor-site', pageUrl: 'https://news.example.com/x' }, cur); await tick();
      out.after = state.local.torSites.slice();""", local={"torSites": ["example.com"]})
    assert r["out"]["title"] == "Stop always opening example.com in Tor" and r["out"]["after"] == [], r["out"]
