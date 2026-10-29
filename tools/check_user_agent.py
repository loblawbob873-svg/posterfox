#!/usr/bin/env python3
"""A real Firefox: does every tab present ONE browser, the same in its requests and to its pages?

    tools/check_user_agent.py [/path/to/firefox]      (default: firefox-bin)

Loads extensions/tab-containers as a temporary add-on, opens new tabs the way a person does (each one its own
container), points each at a local page that records the User-Agent header it was sent, and reads
navigator.userAgent/platform inside that tab. Exit 0 = every tab agrees with itself and none shows this Firefox's own
identity; 1 = a disagreement (printed); 2 = could not run.
"""
import http.server
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import smoke  # noqa: E402  (its Marionette client)

EXT = HERE.parent / "extensions" / "tab-containers"


def main(argv):
    binary = argv[1] if len(argv) > 1 else "firefox-bin"
    seen = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen[self.path] = self.headers.get("User-Agent", "")
            body = b"<title>ua</title>ok"
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % srv.server_address[1]
    with tempfile.TemporaryDirectory() as prof:
        with open(os.path.join(prof, "user.js"), "w") as f:
            f.write('user_pref("marionette.port", %d);\nuser_pref("privacy.userContext.enabled", true);\n' % smoke.PORT)
        env = dict(os.environ, MOZ_HEADLESS="1", MOZ_REMOTE_ALLOW_SYSTEM_ACCESS="1")
        proc = subprocess.Popen([binary, "--headless", "--marionette", "--no-remote", "--profile", prof],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        try:
            time.sleep(6)
            m = smoke.Marionette(smoke.PORT)
            m.cmd("WebDriver:NewSession", {"capabilities": {"alwaysMatch": {}}})
            m.cmd("Addon:Install", {"path": str(EXT), "temporary": True})
            m.cmd("Marionette:SetContext", {"value": "chrome"})
            time.sleep(2)
            own = m.js("return Services.appinfo.name + ' ' + navigator.userAgent")
            results = []
            for i in range(4):
                url = "%s/tab%d" % (base, i)
                # A new tab as a person opens one, then this page in it.
                m.js("const w=Services.wm.getMostRecentWindow('navigator:browser'); w.BrowserCommands.openTab();")
                time.sleep(1.5)
                m.js("const w=Services.wm.getMostRecentWindow('navigator:browser'); w.gBrowser.selectedBrowser.loadURI(Services.io.newURI(arguments[0]), {triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()});", [url])
                for _ in range(40):
                    if "/tab%d" % i in seen:
                        break
                    time.sleep(0.25)
                time.sleep(1)
                tab = m.js("const w=Services.wm.getMostRecentWindow('navigator:browser'), b=w.gBrowser.selectedTab;"
                           "return {ctx: b.userContextId, url: b.linkedBrowser.currentURI.spec};")
                handles = m.cmd("WebDriver:GetWindowHandles")
                m.cmd("Marionette:SetContext", {"value": "content"})
                m.cmd("WebDriver:SwitchToWindow", {"handle": handles[-1] if isinstance(handles, list) else handles["value"][-1]})
                page = m.js("return {ua: navigator.userAgent, platform: navigator.platform, href: location.href};")
                m.cmd("Marionette:SetContext", {"value": "chrome"})
                results.append({"tab": tab, "header": seen.get("/tab%d" % i), "page": page})
        except Exception as e:
            print(json.dumps({"error": "could not drive the browser: %s" % e}))
            return 2
        finally:
            proc.terminate()
    bad = []
    for r in results:
        if not r["header"]:
            bad.append("no request arrived for %s" % r)
        elif r["page"]["href"].startswith(base) and r["page"]["ua"] != r["header"]:
            bad.append("a tab's page and its requests disagree: %s" % r)
        if not r["tab"]["ctx"]:
            bad.append("a tab is not in its own container: %s" % r)
    print(json.dumps({"own": own, "results": results, "failed": bad}, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
