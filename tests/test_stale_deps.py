"""tools/stale_deps.py: the published binary is rebuilt when a library it links against moves in Gentoo.

Without it, nas.lan's morning Gentoo sync moves icu (or nss, or ffmpeg) to a new ABI, a machine's next world update
refuses our PosterFox binary, and Firefox compiles from source on the user's machine.
"""
import importlib.util
import pathlib

import pytest

HERE = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("stale_deps", HERE / "tools" / "stale_deps.py")
sd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sd)

HEADER = "ARCH: amd64\nPACKAGES: 3\nVERSION: 0\n"
OURS = HEADER + """
BUILD_ID: 1
CPV: www-client/posterfox-159.0-r6
RDEPEND: >=dev-libs/nss-3.117:0/0= dev-libs/icu:0/78.1= media-video/ffmpeg:0/59.61.61= x11-libs/gtk+:3 !www-client/firefox:rapid
SLOT: rapid

BUILD_ID: 2
CPV: www-client/posterfox-159.0-r6
RDEPEND: >=dev-libs/nss-3.117:0/0= dev-libs/icu:0/79.1= media-video/ffmpeg:0/59.61.61= x11-libs/gtk+:3
SLOT: rapid
"""


def gentoo(icu="79.1", ffmpeg="59.61.61"):
    return HEADER + f"""
CPV: dev-libs/icu-78.2
SLOT: 0/78.1

CPV: dev-libs/icu-79.1
SLOT: 0/{icu}

CPV: dev-libs/nss-3.118
SLOT: 0

CPV: media-video/ffmpeg-7.1.3
SLOT: 0/{ffmpeg}
"""


def test_a_current_binary_needs_nothing():
    assert sd.stale(OURS, gentoo(), "www-client/posterfox-159.0-r6") == []


def test_a_moved_library_names_itself():
    assert sd.stale(OURS, gentoo(ffmpeg="60.62.62"), "www-client/posterfox-159.0-r6") == [
        ("media-video/ffmpeg", "59.61.61", "60.62.62")]


def test_the_newest_build_is_the_one_judged():
    # Build 1 was against icu 78; build 2 against 79. Gentoo serves 79: nothing to do.
    assert sd.built_against(OURS, "www-client/posterfox-159.0-r6")["dev-libs/icu"] == ("0", "79.1")


def test_the_newest_version_in_a_slot_is_what_machines_get():
    assert sd.current(gentoo())[("dev-libs/icu", "0")] == "79.1"


def test_a_package_that_was_never_published_is_not_called_current():
    with pytest.raises(LookupError):
        sd.stale(OURS, gentoo(), "www-client/posterfox-160.0-r6")


def test_an_unreadable_index_is_exit_2_never_fine(tmp_path):
    assert sd.main(["--ours", str(tmp_path / "missing"), "--gentoo", str(tmp_path / "x"),
                    "--cpv", "www-client/posterfox-159.0-r6"]) == 2


def test_the_command_prints_the_atoms_to_refresh(tmp_path, capsys):
    (tmp_path / "o").write_text(OURS)
    (tmp_path / "g").write_text(gentoo(icu="80.1"))
    assert sd.main(["--ours", str(tmp_path / "o"), "--gentoo", str(tmp_path / "g"),
                    "--cpv", "www-client/posterfox-159.0-r6"]) == 0
    assert capsys.readouterr().out.split() == ["dev-libs/icu"]
