"""Tabs you have not looked at for two minutes go to sleep ("can you automatically put tabs to sleep after 2min ?").

The shipped tabsleep.js under node, with a fake `browser` and the interval run by hand: what is discarded, what never
is (the tab in front, sound, camera/mic/screen, pinned, still loading), and that the add-on actually loads the file.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "extensions" / "tab-containers"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node")

NOW = 10_000_000
OLD = NOW - 3 * 60 * 1000          # last looked at three minutes ago
FRESH = NOW - 30 * 1000            # thirty seconds ago


def _sweep(tabs):
    js = r"""
const fs = require('fs'), vm = require('vm');
const tabs = %s, discarded = []; let tick = null;
const browser = { tabs: { query: async () => tabs, discard: async id => { discarded.push(id); } } };
const ctx = vm.createContext({ browser, console, Date: { now: () => %d }, setInterval: (f, ms) => { tick = f; } });
vm.runInContext(fs.readFileSync(%s, 'utf8'), ctx);
(async () => { await tick(); console.log(JSON.stringify(discarded)); })();
""" % (json.dumps(tabs), NOW, json.dumps(str(EXT / "tabsleep.js")))
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _tab(i, **kw):
    t = {"id": i, "url": "https://example.org/%d" % i, "active": False, "discarded": False, "pinned": False,
         "audible": False, "status": "complete", "lastAccessed": OLD}
    t.update(kw)
    return t


def test_a_tab_left_alone_for_two_minutes_sleeps_and_a_recent_one_does_not():
    assert _sweep([_tab(1), _tab(2, lastAccessed=FRESH)]) == [1]


@pytest.mark.parametrize("why", [{"active": True}, {"audible": True}, {"pinned": True}, {"status": "loading"},
                                 {"discarded": True}, {"sharingState": {"camera": True}},
                                 {"sharingState": {"microphone": True}}, {"sharingState": {"screen": "Screen"}},
                                 {"url": "about:newtab"}])
def test_never_put_to_sleep(why):
    assert _sweep([_tab(1, **why)]) == [], why


def test_the_add_on_loads_it():
    m = json.loads((EXT / "manifest.json").read_text())
    assert "tabsleep.js" in m["background"]["scripts"]
    assert "tabs" in m["permissions"]
