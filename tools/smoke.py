#!/usr/bin/env python3
"""Check a BUILT PosterFox before it is published: start it headless and ask it, over Marionette (Firefox's own
remote protocol, so nothing to install), what a user would otherwise find out by using it.

    tools/smoke.py /usr/lib64/posterfox/posterfox            # an installed PosterFox
    tools/smoke.py <image>/usr/lib64/posterfox/posterfox     # straight out of a build's image/ directory

Prints one JSON report and exits 0 only when every check passed. Checks: it is PosterFox (name, telemetry compiled
out), the enterprise policies are active, uBlock Origin + Privacy Badger + the tab-container add-on + the cyberpunk theme
are installed and enabled, history/form history are off and everything but passwords is cleared on exit, the window
stylesheet is registered, and the codecs a browser needs answer "probably"/"maybe" (H.264/AAC through the system
FFmpeg, VP9/AV1/Opus/FLAC/MP3 built in). Python standard library only, so it runs on the build VM and on a machine.
"""
import http.server
import json
import os
import socket
import threading
import subprocess
import sys
import tempfile
import time

PORT = int(os.environ.get("POSTERFOX_MARIONETTE_PORT", "2829"))

CODECS = {
    "h264": 'video/mp4; codecs="avc1.42E01E"',
    "aac": 'audio/mp4; codecs="mp4a.40.2"',
    "vp9": 'video/webm; codecs="vp9"',
    "av1": 'video/mp4; codecs="av01.0.05M.08"',
    "opus": 'audio/ogg; codecs="opus"',
    "flac": "audio/flac",
    "mp3": "audio/mpeg",
}
ADDONS = {"uBlock0@raymondhill.net": "uBlock Origin", "jid1-MnnxcxisBPnSXQ@jetpack": "Privacy Badger",
          "passwords@poster.place": "PosterChan Passwords",
          "tab-containers@posterfox.poster.place": "tab containers", "cyberpunk-theme@poster.place": "cyberpunk theme"}


class Marionette:
    def __init__(self, port):
        deadline = time.time() + 60
        while True:
            try:
                self.s = socket.create_connection(("127.0.0.1", port), timeout=30)
                break
            except OSError:
                if time.time() > deadline:
                    raise
                time.sleep(0.3)
        self.id = 0
        self._read()                                        # the server's hello

    def _read(self):
        buf = b""
        while b":" not in buf:
            buf += self.s.recv(1)
        n, rest = buf.split(b":", 1)
        n = int(n)
        while len(rest) < n:
            rest += self.s.recv(n - len(rest))
        return json.loads(rest)

    def cmd(self, name, params=None):
        self.id += 1
        body = json.dumps([0, self.id, name, params or {}]).encode()
        self.s.sendall(str(len(body)).encode() + b":" + body)
        while True:
            m = self._read()
            if isinstance(m, list) and m[1] == self.id:
                if m[2]:
                    raise RuntimeError("%s: %s" % (name, m[2]))
                return m[3]

    def js(self, script, args=None, asynchronous=False):
        r = self.cmd("WebDriver:ExecuteAsyncScript" if asynchronous else "WebDriver:ExecuteScript",
                     {"script": script, "args": args or []})
        return r.get("value") if isinstance(r, dict) else r


CHROME_STATE = r"""
const P = Services.prefs;
const get = (k) => { try { switch (P.getPrefType(k)) { case P.PREF_BOOL: return P.getBoolPref(k);
  case P.PREF_INT: return P.getIntPref(k); case P.PREF_STRING: return P.getStringPref(k); } } catch (e) {} return null; };
const css = Services.dirsvc.get("GreD", Ci.nsIFile); css.append("posterchan"); css.append("posterfox-chrome.css");
const sss = Cc["@mozilla.org/content/style-sheet-service;1"].getService(Ci.nsIStyleSheetService);
let brand = ""; try { brand = Services.strings.createBundle("chrome://branding/locale/brand.properties").GetStringFromName("brandShortName"); } catch (e) {}
return {
  name: Services.appinfo.name, version: Services.appinfo.version, brand,
  telemetryBuilt: AppConstants.MOZ_TELEMETRY_REPORTING,
  policiesActive: Services.policies.status === Services.policies.ACTIVE,
  policies: Object.keys(Services.policies.getActivePolicies() || {}).sort(),
  prefs: Object.fromEntries(["places.history.enabled", "browser.formfill.enable", "privacy.sanitize.sanitizeOnShutdown",
    "privacy.clearOnShutdown_v2.historyFormDataAndDownloads", "privacy.clearOnShutdown_v2.cookiesAndStorage",
    "privacy.clearOnShutdown_v2.cache", "privacy.userContext.enabled",
    "toolkit.telemetry.enabled", "datareporting.healthreport.uploadEnabled", "browser.tabs.inTitlebar",
    "identity.fxaccounts.enabled"].map(k => [k, get(k)])),
  chromeCss: css.exists() && sss.sheetRegistered(Services.io.newFileURI(css), sss.USER_SHEET),
  themeFrame: (() => { try { const w = Services.wm.getMostRecentWindow("navigator:browser"); if (!w) return null;
    // Firefox 159 draws a theme's theme_frame on the window's <body>, under a transparent toolbox (measured on the
    // portable build, 2026-10-29); older ones on #navigator-toolbox. Both are read, and what sits over it.
    const tb = w.document.getElementById("TabsToolbar"), box = w.document.getElementById("navigator-toolbox");
    const bodyImg = w.getComputedStyle(w.document.body).backgroundImage, boxImg = w.getComputedStyle(box).backgroundImage;
    return { tabsBg: w.getComputedStyle(tb).backgroundColor, tabsImg: w.getComputedStyle(tb).backgroundImage,
             frame: boxImg.includes("url(") ? boxImg : bodyImg,
             boxBg: boxImg.includes("url(") ? "rgba(0, 0, 0, 0)" : w.getComputedStyle(box).backgroundColor };
  } catch (e) { return { error: String(e) }; } })(),
};
"""
CHROME_NEWTAB = r"""
try { const {AboutNewTab} = ChromeUtils.importESModule("resource:///modules/AboutNewTab.sys.mjs");
  const st = AboutNewTab.activityStream && AboutNewTab.activityStream.store && AboutNewTab.activityStream.store.getState();
  return st && st.TopSites && st.TopSites.initialized ? st.TopSites.rows.map(r => r.url) : null;
} catch (e) { return null; }
"""
NEWTAB = ["https://poster.place/", "/posterchanai", "/posterfox", "addons.mozilla.org/firefox/addon/posterchan-passwords/"]
TOR_OPEN = r"""
const {ContextualIdentityService} = ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
const w = Services.wm.getMostRecentWindow('navigator:browser'), sp = Services.scriptSecurityManager.getSystemPrincipal();
const tor = ContextualIdentityService.create('PosterFox Tor tab 990', 'fingerprint', 'purple');
const plain = ContextualIdentityService.create('PosterFox tab 991', 'circle', 'blue');
for (const [c, u] of [[tor, arguments[0]], [plain, arguments[1]]])
  w.gBrowser.addTab(u, { userContextId: c.userContextId, triggeringPrincipal: sp });
return true;
"""
CHROME_ADDONS = r"""
const done = arguments[arguments.length - 1];
const { AddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
AddonManager.getAllAddons().then(all => done(all.map(a => ({ id: a.id, active: a.isActive, type: a.type, name: a.name }))),
                                 e => done({ error: String(e) }));
"""
CHROME_TABS = r"""
const win = Services.wm.getMostRecentWindow("navigator:browser");
const css = (sel) => { const e = win.document.querySelector(sel); return e ? win.getComputedStyle(e).display : "missing"; };
return { tabs: [...win.gBrowser.tabs].map(t => ({ url: t.linkedBrowser.currentURI.spec, ctx: t.userContextId })),
         // Maximise and Restore swap with the window state; the one that applies must be shown.
         buttons: { min: css(".titlebar-buttonbox .titlebar-min"),
                    max: css(win.document.documentElement.getAttribute("sizemode") === "maximized"
                             ? ".titlebar-buttonbox .titlebar-restore" : ".titlebar-buttonbox .titlebar-max"),
                    close: css(".titlebar-buttonbox .titlebar-close") } };
"""
CHROME_CONTAINERS = r"""
const done = arguments[arguments.length - 1];
const win = Services.wm.getMostRecentWindow("navigator:browser");
const before = win.gBrowser.tabs.length;
// A NEW TAB THE WAY A PERSON OPENS ONE (Ctrl+T / +: about:newtab) -- not about:blank, which every page tab starts as
// and which the add-on deliberately leaves alone (that is what kept Settings and the uBlock dashboard out of
// containers, 2026-10-29). And Settings itself, which must stay a plain tab showing Settings.
for (let i = 0; i < 2; i++) win.BrowserCommands.openTab();
setTimeout(() => {
  const tabs = [...win.gBrowser.tabs].map(t => t.userContextId);
  // From the first (page) tab: Settings opened over a blank new tab would reuse that tab instead.
  win.gBrowser.selectedTab = win.gBrowser.tabs[0];
  win.openPreferences();
  setTimeout(() => done({ before, tabs,
    settings: [...win.gBrowser.tabs].filter(t => t.linkedBrowser.currentURI.spec.startsWith("about:preferences"))
                                    .map(t => t.userContextId) }), 3000);
}, 4000);
"""


def _local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))                          # no packet is sent: this only picks the outgoing address
        return s.getsockname()[0]
    finally:
        s.close()


def _tor_check(m):
    seen = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            self.send_response(200); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b"ok")

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = "http://%s:%d" % (_local_ip(), srv.server_address[1])
        m.js(TOR_OPEN, [base + "/tor-tab", base + "/plain-tab"])
        for _ in range(20):
            if "/plain-tab" in seen:
                break
            time.sleep(0.5)
        time.sleep(4)                                           # long enough for a leak to arrive too
        return {"plain": "/plain-tab" in seen, "leaked": "/tor-tab" in seen}
    finally:
        srv.shutdown()


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    binary = argv[1]
    report, failed = {}, []
    # The link a first start is handed, the way every link from the desktop reaches the browser (`posterfox <url>`).
    page = http.server.ThreadingHTTPServer(("127.0.0.1", 0), type("Quiet", (http.server.BaseHTTPRequestHandler,), {
        "do_GET": lambda self: (self.send_response(200), self.send_header("Content-Type", "text/html"), self.end_headers(),
                                self.wfile.write(b"<title>PosterFox link</title>link")),
        "log_message": lambda self, *a: None}))
    threading.Thread(target=page.serve_forever, daemon=True).start()
    link = "http://127.0.0.1:%d/from-the-desktop" % page.server_address[1]
    with tempfile.TemporaryDirectory() as prof:
        with open(os.path.join(prof, "user.js"), "w") as f:
            f.write('user_pref("marionette.port", %d);\n' % PORT)
        env = dict(os.environ, MOZ_HEADLESS="1", MOZ_CRASHREPORTER_DISABLE="1", MOZ_REMOTE_ALLOW_SYSTEM_ACCESS="1")
        proc = subprocess.Popen([binary, "--headless", "--marionette", "--no-remote", "--profile", prof, link],
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env)
        try:
            m = Marionette(PORT)
            # The first window can still be settling (distribution add-ons install at first start, and the tab-container
            # add-on re-opens the first tab in a container): a session made in that moment finds no content browser.
            time.sleep(6)
            for attempt in range(6):
                try:
                    m.cmd("WebDriver:NewSession", {"capabilities": {"alwaysMatch": {"acceptInsecureCerts": True}}})
                    break
                except RuntimeError:
                    if attempt == 5:
                        raise
                    time.sleep(3)
            m.cmd("Marionette:SetContext", {"value": "chrome"})
            report.update(m.js(CHROME_STATE))
            report["startup"] = m.js(CHROME_TABS)
            report["addons"] = m.js(CHROME_ADDONS, asynchronous=True)
            report["containers"] = m.js(CHROME_CONTAINERS, asynchronous=True)
            # TOR TABS NEVER GO DIRECT: a Tor tab and an ordinary one both ask for a page on this machine's own
            # (non-loopback) address. Without Tor the Tor tab must fail; with Tor, Tor cannot reach a private
            # address either -- so in both cases only the ordinary tab may arrive.
            report["tor"] = _tor_check(m)
            report["newtab"] = None
            for _ in range(20):                               # the new tab's feed initialises a moment after start
                report["newtab"] = m.js(CHROME_NEWTAB)
                if report["newtab"]:
                    break
                time.sleep(1)
            m.cmd("Marionette:SetContext", {"value": "content"})
            m.cmd("WebDriver:Navigate", {"url": "data:text/html,<title>codecs</title><video></video>"})
            report["codecs"] = m.js("const v=document.createElement('video');return Object.fromEntries(Object.entries(arguments[0]).map(([k,t])=>[k,v.canPlayType(t)]));", [CODECS])
            m.cmd("WebDriver:DeleteSession")
        except Exception as e:                               # noqa: BLE001 -- report it, never hang a release
            report["error"] = str(e)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()

    def need(ok, what):
        if not ok:
            failed.append(what)
    if "error" in report:
        failed.append("could not drive the browser: " + report["error"])
    else:
        need(report.get("brand") == "PosterFox", "branding (brandShortName is %r)" % report.get("brand"))
        need(report.get("telemetryBuilt") is False, "telemetry is compiled in")
        need(report.get("policiesActive"), "enterprise policies are not active")
        need("DisableFirefoxAccounts" in (report.get("policies") or []), "Mozilla accounts are not disabled by policy")
        p = report.get("prefs", {})
        need(p.get("places.history.enabled") is False, "history is remembered")
        need(p.get("browser.formfill.enable") is False, "form history is remembered")
        need(p.get("privacy.sanitize.sanitizeOnShutdown") is True, "data is not cleared on exit")
        need(p.get("privacy.userContext.enabled") is True, "containers are off")
        need(p.get("toolkit.telemetry.enabled") is False, "telemetry is enabled")
        need(p.get("identity.fxaccounts.enabled") is False, "Mozilla accounts (Sync sign-in) are enabled")
        need(report.get("chromeCss") is True, "the PosterChan window stylesheet is not registered")
        tf = report.get("themeFrame") or {}
        need("url(" in (tf.get("frame") or ""), "the PosterChan theme's banner is not on the toolbar (%s)" % tf)
        need((tf.get("boxBg") or "") in ("rgba(0, 0, 0, 0)", "transparent"), "the toolbox is painted over the PosterChan theme's banner (%s)" % tf)
        need((tf.get("tabsBg") or "") in ("rgba(0, 0, 0, 0)", "transparent") and (tf.get("tabsImg") or "none") == "none",
             "the tab strip is painted over the PosterChan theme's banner (%s)" % tf)
        ads = {a["id"]: a for a in report.get("addons") or [] if isinstance(a, dict)}
        for aid, name in ADDONS.items():
            need(aid in ads and ads[aid]["active"], name + " is missing or disabled")
        t = report.get("tor") or {}
        need(t.get("plain") is True, "the Tor tab check did not run (the ordinary tab never arrived): %s" % t)
        need(t.get("leaked") is False, "a TOR TAB REACHED THE NETWORK DIRECTLY")
        tiles = report.get("newtab") or []
        need(len(tiles) == len(NEWTAB) and all(any(t.endswith(w) or w in t for t in tiles) for w in NEWTAB),
             "the new tab's shortcuts are not PosterChan's (%s)" % tiles)
        st = report.get("startup") or {}
        first = st.get("tabs") or []
        need(len(first) == 1 and first[0]["url"] == link,
             "a first start with a link must show exactly that one tab (got %s)" % [t["url"] for t in first])
        need(bool(first) and first[0]["ctx"] != 0, "the link a first start was handed is not in a container of its own")
        for b, d in (st.get("buttons") or {}).items():
            need(d not in ("none", "missing"), "the %s window button is not shown" % b)
        tabs = (report.get("containers") or {}).get("tabs") or []
        need(len(tabs) >= 3 and len(set(t for t in tabs if t)) >= 3, "new tabs are not each in their own container (%s)" % tabs)
        st = (report.get("containers") or {}).get("settings")
        need(st == [0], "Settings did not open as a plain tab showing Settings (%s)" % st)
        for k, v in (report.get("codecs") or {}).items():
            need(v in ("probably", "maybe"), "cannot play " + k)
    report["failed"] = failed
    print(json.dumps(report, indent=1, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
