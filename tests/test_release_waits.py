"""The daily release runs after the day's Gentoo sync -- checked, not assumed -- and waits out a running deploy.

"shouldn't the firefox maintenance tasks for the repo run after the daily repo sync?" (2026-10-29). The timer fires at
07:30, after nas.lan's 06:00 sync, but a sync that ran long or failed was invisible, and a deploy in progress made the
run give up for the whole day (07:46 that morning). release.sh's own `synced_today`, run under bash with `ssh` stubbed.
"""
import datetime
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SH = (ROOT / "tools/release.sh").read_text()


def _synced(tmp_path, active, status, when):
    fn = re.search(r"^synced_today\(\) \{.*?^\}", SH, re.S | re.M).group(0)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "ssh").write_text("#!/bin/sh\nprintf '%s\\n%s\\n%s\\n' '" + active + "' '" + status + "' '" + when + "'\n")
    (bindir / "ssh").chmod(0o755)
    r = subprocess.run(["bash", "-c", fn + "\nsynced_today && echo yes || echo no"], capture_output=True, text=True,
                       env={**os.environ, "PATH": f"{bindir}:/usr/bin:/bin", "NAS": "nas.test"}, timeout=20)
    return r.stdout.strip()


TODAY = datetime.datetime.now().strftime("%a %Y-%m-%d 06:20:14")
YESTERDAY = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%a %Y-%m-%d 06:20:14")


@pytest.mark.parametrize("active,status,when,want", [
    ("inactive", "0", TODAY, "yes"),                 # finished this morning, successfully
    ("activating", "0", YESTERDAY, "no"),            # running right now
    ("inactive", "0", YESTERDAY, "no"),              # today's has not happened
    ("failed", "1", TODAY, "no"),                    # today's failed
])
def test_the_sync_is_checked_not_assumed(tmp_path, active, status, when, want):
    assert _synced(tmp_path, active, status, when) == want


def test_a_running_deploy_is_waited_out_and_the_tarball_follows():
    assert "a deploy is running -- not starting one beside it\"; exit 0" not in SH
    assert re.search(r"while deploying; do", SH) and "POSTERFOX_DEPLOY_WAIT_MIN" in SH
    assert SH.index("until synced_today") < SH.index("while deploying") < SH.index("# ---------------------------------------------------------------- 1. what should be published")
    assert SH.count("portable_follow; exit 0") == 2          # after publishing, and when it was already published
