"""PosterFox: every tab presents ONE real browser, the same in its requests and to its pages ("we need to randomly
change the user agent for each tab to real browsers (chrome,firefox,brave,etc)", 2026-10-29).

The shipped useragent.js + background.js under node, against the fake `browser` of test_tab_containers.py.
"""
import json
import re
import shutil
import subprocess

import pytest

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_tab_containers import EXT, run, tab  # noqa: E402  (the shared fake browser)

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node")


def agent(js):
    code = "const A=require(%s); console.log(JSON.stringify((()=>{%s})()));" % (json.dumps(str(EXT / "useragent.js")), js)
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=20)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_a_tabs_requests_and_its_pages_name_the_same_browser():
    r = run([tab(1, "https://a.example")], [], """
      await L.req({ type: 'main_frame', tabId: 1, url: 'https://a.example/' }); await tick();
      const t = (await browser.tabs.query({}))[0];
      const res = L.headers({ cookieStoreId: t.cookieStoreId, requestHeaders: [{ name: 'User-Agent', value: 'real one' }, { name: 'Accept', value: '*/*' }] });
      out.headers = res.requestHeaders; out.store = t.cookieStoreId;""")
    scripts = [s for s in r["scripts"] if s["store"] == r["out"]["store"]]
    assert len(scripts) == 1 and scripts[0]["runAt"] == "document_start" and scripts[0]["allFrames"], r["scripts"]
    page = json.loads(re.search(r"const v=(\{.*?\}),w=", scripts[0]["code"]).group(1))
    sent = [h["value"] for h in r["out"]["headers"] if h["name"].lower() == "user-agent"]
    assert sent == [page["userAgent"]], ("the header and the page disagree", sent, page)
    assert "real one" not in sent and {"name": "Accept", "value": "*/*"} in r["out"]["headers"]


def test_a_tab_without_an_identity_is_left_alone_and_a_closed_tab_takes_its_script_with_it():
    r = run([tab(1, "https://a.example")], [], """
      out.default = L.headers({ cookieStoreId: 'firefox-default', requestHeaders: [{ name: 'User-Agent', value: 'x' }] });
      await L.req({ type: 'main_frame', tabId: 1, url: 'https://a.example/' }); await tick();
      const t = (await browser.tabs.query({}))[0]; out.store = t.cookieStoreId;
      await browser.tabs.remove(t.id); await tick();""")
    assert r["out"]["default"] == {}, "a request outside our containers was rewritten"
    assert r["unregistered"] == [r["out"]["store"]], r


def test_only_real_browsers_at_versions_that_exist():
    v = agent("return A.versions(159, new Date('2026-10-29T00:00:00Z'))")
    assert v == {"ff": 159, "chrome": 158, "safari": 27}
    assert agent("return A.versions(159, new Date('2026-08-01T00:00:00Z')).safari") == 26, "Safari's year starts in September"
    ps = agent("return A.profiles(A.versions(159, new Date('2026-10-29T00:00:00Z')))")
    by = {p["id"]: p for p in ps}
    assert set(by) == {"chrome-win", "chrome-mac", "chrome-linux", "edge-win", "brave-win", "firefox-win", "firefox-mac", "firefox-linux", "safari-mac"}
    assert by["brave-win"]["ua"] == by["chrome-win"]["ua"], "Brave sends Chrome's exact string"
    assert by["edge-win"]["ua"].endswith(" Edg/158.0.0.0")
    assert "Chrome/158.0.0.0 Safari/537.36" in by["chrome-mac"]["ua"] and "Firefox/159.0" in by["firefox-linux"]["ua"]
    assert "Version/27.0 Safari/605.1.15" in by["safari-mac"]["ua"] and by["safari-mac"]["vendor"] == "Apple Computer, Inc."
    for p in ps:
        assert p["ua"].startswith("Mozilla/5.0 (") and p["appVersion"] == p["ua"][len("Mozilla/"):], p
        assert p["platform"] == {"Windows": "Win32", "Macintosh": "MacIntel", "X11": "Linux x86_64"}[p["ua"].split("(")[1].split(";")[0].split(" ")[0]], p


def test_every_tor_tab_looks_the_same():
    ids = agent("const L=A.profiles(A.versions(159)); return [0,0.3,0.6,0.99].map(r=>A.pick(L,true,r).id)")
    assert set(ids) == {"firefox-win"}
    spread = agent("const L=A.profiles(A.versions(159)); return [...new Set([...Array(9)].map((_,i)=>A.pick(L,false,i/9).id))].length")
    assert spread == 9, "ordinary tabs do not range over every identity"


def test_the_page_script_changes_what_a_page_reads_from_navigator():
    got = agent("""
      const p = A.profiles(A.versions(159))[0];
      const nav = { userAgent: 'PosterFox', platform: 'Linux x86_64', appVersion: 'x', vendor: '' };
      const window = { wrappedJSObject: { navigator: nav } };
      const exportFunction = f => f;
      new Function('window', 'exportFunction', A.pageCode(p))(window, exportFunction);
      return { ua: nav.userAgent, platform: nav.platform, vendor: nav.vendor, want: p.ua };""")
    assert got["ua"] == got["want"] and got["platform"] == "Win32" and got["vendor"] == "Google Inc.", got
