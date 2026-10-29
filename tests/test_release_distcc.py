"""The PosterFox build spreads its C/C++ over the distcc hosts -- set up for that one emerge, never in the VM's image.

"set up distcc for the posterfox builds, i have distcc on the hosts for a reason to speed up firefox compile times!"
(2026-10-29). The build VM's disk becomes the ISO, so distcc cannot live in its /etc/portage (a package.env entry there
shipped a LAN host list in the 2026-10-29 ISO) or in its installed packages. release.sh's build step, run under bash
with the VM stubbed: it records every command the VM would run and answers the compiler probes.
"""
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SH = (ROOT / "tools/release.sh").read_text()
STEP = SH[SH.index("DCC=/var/tmp-build/distcc"):SH.index('GPKG=$(vm "ls -t')]


def _run(tmp_path, answers):
    """answers: distcc host ip -> the clang version that host compiles with ('' = no answer)."""
    log = tmp_path / "vm.log"
    stub = r'''
vm() { printf '%s\n' "$*" >> "$VMLOG"
  case "$*" in
    *"DISTCC_HOSTS="*"clang -c probe.c"*) ip=$(printf '%s' "$*" | sed -n 's/.*DISTCC_HOSTS=\([0-9.]*\).*/\1/p'); eval "v=\${ANS_$(printf '%s' "$ip" | tr . _)}"; [ -n "$v" ] && printf '%s \n' "$v";;
    *"clang -c probe.c"*) printf '22.1.8 \n';;
  esac; return 0; }
ssh() { cat >/dev/null 2>&1; return 0; }
say() { printf 'SAY %s\n' "$*"; }
die() { printf 'DIE %s\n' "$*"; exit 9; }
'''
    env = {**os.environ, "VMLOG": str(log), "LOG": str(tmp_path / "release.log"), "NAS": "nas.test", "WANT": "posterfox-159.0-r12"}
    for ip, v in answers.items():
        env["ANS_" + ip.replace(".", "_")] = v
    r = subprocess.run(["bash", "-c", stub + STEP], capture_output=True, text=True, env=env, timeout=30)
    return r.stdout, log.read_text() if log.exists() else ""


def _emerge(cmds):
    lines = [l for l in cmds.splitlines() if "emerge --oneshot --buildpkgonly" in l]
    assert len(lines) == 1, cmds
    return lines[0]


def test_both_hosts_compile_when_they_run_the_vms_clang(tmp_path):
    out, cmds = _run(tmp_path, {"192.168.0.2": "22.1.8", "192.168.122.1": "22.1.8"})
    e = _emerge(cmds)
    assert "FEATURES=distcc" in e and "192.168.0.2/12,lzo" in e and "192.168.122.1/8,lzo" in e, e
    assert "mount --bind /var/tmp-build/distcc/masq /usr/lib/distcc/bin" in e and "trap 'umount /usr/lib/distcc/bin" in e, e
    assert "-j24" in e, ("the job count is the hosts' slots + 4 local", e)


def test_a_host_with_another_clang_is_left_out_and_said_so(tmp_path):
    out, cmds = _run(tmp_path, {"192.168.0.2": "21.1.0", "192.168.122.1": "22.1.8"})
    e = _emerge(cmds)
    assert "192.168.0.2" not in e and "192.168.122.1/8,lzo" in e, e
    assert "not using 192.168.0.2" in out, out


def test_no_host_means_a_local_build_without_distcc(tmp_path):
    out, cmds = _run(tmp_path, {"192.168.0.2": "", "192.168.122.1": ""})
    e = _emerge(cmds)
    assert "FEATURES=distcc" not in e and "mount --bind" not in e, e
    assert "building on the VM alone" in out, out


def test_nothing_is_written_into_the_vms_image(tmp_path):
    out, cmds = _run(tmp_path, {"192.168.0.2": "22.1.8", "192.168.122.1": "22.1.8"})
    assert "/etc/portage" not in cmds and "emerge" not in cmds.replace("emerge --oneshot --buildpkgonly", ""), cmds
    first, last = cmds.splitlines()[0], cmds.splitlines()[-1]
    for line in (first, last):      # cleared before (a run that died) and after the build
        assert "umount /usr/lib/distcc/bin" in line and "rmdir /usr/lib/distcc/bin /usr/lib/distcc" in line, cmds
    assert not re.search(r"(^|[ ;])(cp|install|ln)[^;]*(/usr/(bin|lib)/distcc)( |;|$)", cmds.replace("/usr/lib/distcc/bin", "")), cmds
