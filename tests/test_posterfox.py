"""PosterFox's build inputs: the ebuild generator, the launcher, the branding images, the policies, the autoconfig.

Run: python3 -m pytest tests/  (needs Pillow; node for the autoconfig check)
The Gentoo ebuild under tests/fixtures is a real one (firefox-158.0); a newer tree is checked too when present.
"""
import importlib.util
import json
import pathlib
import re
import shutil
import subprocess

import pytest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
FIX = HERE / "fixtures"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ME = _load("make_ebuild", ROOT / "tools" / "make-ebuild.py")
MB = _load("make_branding", ROOT / "tools" / "make-branding.py")


def _gen(src=None):
    return ME.transform(src or (FIX / "firefox-159.0.ebuild").read_text(), 1)


def test_the_generated_ebuild_is_valid_bash(tmp_path):
    p = tmp_path / "posterfox-159.0-r1.ebuild"
    p.write_text(_gen())
    r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_telemetry_is_compiled_out_and_cannot_be_turned_on():
    t = _gen()
    assert not re.search(r"\buse telemetry\b", t)
    assert "+telemetry" not in t and " telemetry " not in re.search(r'IUSE\+=" \+gmp-autoupdate[^"]*"', t).group(0)
    for flag in ("MOZ_TELEMETRY_REPORTING=0", "MOZ_DATA_REPORTING=0", "MOZ_CRASHREPORTER=0"):
        assert flag in t
    assert "if ! false; then" in t and "if false; then" in t


def test_branding_name_profiles_and_ublock():
    t = _gen()
    assert "--with-branding=browser/branding/posterfox" in t and "--enable-official-branding" not in t
    assert "--with-app-name=posterfox" in t and "--with-app-basename=PosterFox" in t
    assert 'imply_option("MOZ_APP_PROFILE", "mozilla/firefox")' in t, "switching from firefox-bin must keep the profile"
    assert "mozconfig_add_options_ac 'PosterFox: keep firefox profiles'" not in t, "configure refuses MOZ_APP_PROFILE from a mozconfig"
    assert 'MOZ_PN="firefox"' in t and 'S="${WORKDIR}/${MOZ_PN}-${PV%_*}"' in t
    assert "uBlock0_${POSTERFOX_UBO}.firefox.signed.xpi -> posterfox-ublock0-${POSTERFOX_UBO}.xpi" in t
    assert 'POSTERFOX_UBO="%s"' % json.loads((ROOT / "pins.json").read_text())["ublock_origin"] in t
    assert "!www-client/firefox" not in t and "firefox-l10n" not in t
    assert "posterfox_branding" in t and "posterfox_distribution" in t


def test_a_changed_upstream_line_stops_the_generator():
    src = (FIX / "firefox-159.0.ebuild").read_text().replace("--enable-official-branding", "--enable-official-brandingX")
    with pytest.raises(SystemExit) as e:
        _gen(src)
    assert "branding configure flags" in str(e.value)


def test_the_launcher_runs_posterfox():
    w = ME.wrapper((FIX / "firefox-files" / "firefox-r1.sh").read_text())
    assert 'MOZ_FIREFOX_FILE="posterfox"' in w and 'MOZILLA_FIVE_HOME="${MOZ_LIB_DIR}/posterfox"' in w
    assert "/firefox/" not in w.split("##\n## Enable Wayland")[0]


def test_newest_firefox_skips_esr_and_rc(tmp_path):
    for v in ("157.0", "158.0", "158.0.1", "140.4.0_p1", "159.0_rc1", "128.13.0esr"):
        (tmp_path / f"firefox-{v}.ebuild").write_text("")
    assert ME.newest_firefox(tmp_path) == "158.0.1"


def test_the_full_package_dir(tmp_path):
    gentoo = tmp_path / "gentoo"
    gentoo.mkdir()
    shutil.copy(FIX / "firefox-159.0.ebuild", gentoo / "firefox-159.0.ebuild")
    shutil.copytree(FIX / "firefox-files", gentoo / "files")
    (ROOT / "build" / "files-posterfox").mkdir(parents=True, exist_ok=True)
    out = tmp_path / "posterfox"
    ME.main(["--gentoo", str(gentoo), "--version", "159.0", "--out", str(out), "--rev", "3"])
    assert (out / "posterfox-159.0-r3.ebuild").exists()
    assert (out / "files" / "posterfox-r1.sh").exists() and (out / "files" / "posterfox").is_dir()


def test_branding_images_have_mozillas_sizes(tmp_path):
    from PIL import Image
    names = MB.write(tmp_path)
    for s in (16, 22, 24, 32, 48, 64, 128, 256):
        assert Image.open(tmp_path / f"default{s}.png").size == (s, s)
    assert Image.open(tmp_path / "content" / "about-logo@2x.png").size == (384, 384)
    assert Image.open(tmp_path / "content" / "about.png").size == (300, 236)
    assert "context-fill" in (tmp_path / "content" / "about-wordmark.svg").read_text()
    again = tmp_path / "again"
    MB.write(again)
    assert all((tmp_path / n).read_bytes() == (again / n).read_bytes() for n in names), "branding is not deterministic"


def test_brand_strings_say_posterfox_and_keep_the_firefox_trademark_notice():
    ftl = (ROOT / "branding" / "locales" / "en-US" / "brand.ftl").read_text()
    assert "-brand-short-name = PosterFox" in ftl and "not affiliated" in ftl
    assert "MOZ_APP_DISPLAYNAME=PosterFox" in (ROOT / "branding" / "configure.sh").read_text()


def test_policies_turn_off_telemetry_and_force_ublock():
    p = json.loads((ROOT / "distribution" / "policies.json").read_text())["policies"]
    assert p["DisableTelemetry"] and p["DisableFirefoxStudies"] and p["DisablePocket"]
    ub = p["ExtensionSettings"]["uBlock0@raymondhill.net"]
    assert ub["installation_mode"] == "force_installed"
    assert ub["install_url"] == "file:///usr/lib64/posterfox/distribution/extensions/uBlock0@raymondhill.net.xpi"


def test_app_scope_addons_are_enabled_and_the_theme_is_default():
    prefs = (ROOT / "distribution" / "posterfox-prefs.js").read_text()
    assert 'pref("extensions.autoDisableScopes", 11);' in prefs
    assert 'pref("extensions.activeThemeID", "cyberpunk-theme@poster.place");' in prefs
    assert 'general.config.filename", "posterfox.cfg"' in (ROOT / "distribution" / "autoconfig.js").read_text()


@pytest.mark.skipif(shutil.which("node") is None, reason="node")
@pytest.mark.parametrize("instance,want", [
    ("https://poster.place", "https://poster.place/client?pcai=1"),
    ("https://poster.place/", "https://poster.place/client?pcai=1"),
    ("http://192.168.0.2:3051", "http://192.168.0.2:3051/client?pcai=1"),
    ("javascript:alert(1)", None),
    ("https://evil.example/path?x", None),
    ("", None),
])
def test_the_autoconfig_points_the_ai_sidebar_at_this_computers_instance(tmp_path, instance, want):
    """Runs the shipped posterfox.cfg under node with Firefox's autoconfig globals faked: Home has the PosterChan
    desktop's config.json, defaultPref records what it sets. Only a plain origin may become the sidebar URL."""
    home = tmp_path / "home"
    (home / ".config" / "posterchan-desktop").mkdir(parents=True)
    (home / ".config" / "posterchan-desktop" / "config.json").write_text(json.dumps({"instance": instance}))
    cfg = (ROOT / "distribution" / "posterfox.cfg").read_text()
    js = r"""
const fs=require('fs'),path=require('path'); const set={};
function file(p){ return { p, append(x){ this.p=path.join(this.p,x); }, exists(){ return fs.existsSync(this.p); },
  get fileSize(){ return fs.statSync(this.p).size; } }; }
globalThis.defaultPref=(k,v)=>{ set[k]=v; };
globalThis.Services={ dirsvc:{ get:(k)=>file(k==='Home'?%s:'/nonexistent') }, io:{ newFileURI:()=>({}) } };
let reading=null;
globalThis.Components={ classes:{
  '@mozilla.org/network/file-input-stream;1':{ createInstance:()=>({ init(f){ reading=f.p; } }) },
  '@mozilla.org/intl/converter-input-stream;1':{ createInstance:()=>{ let done=false; return { init(){}, close(){},
     readString(n,o){ if(done) return 0; done=true; o.value=fs.readFileSync(reading,'utf8'); return o.value.length; } }; } },
  '@mozilla.org/content/style-sheet-service;1':{ getService:()=>({}) } },
  interfaces:{ nsIFile:{}, nsIFileInputStream:{}, nsIConverterInputStream:{}, nsIStyleSheetService:{} } };
eval(%s);
console.log(JSON.stringify(set));
""" % (json.dumps(str(home)), json.dumps(cfg))
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout).get("browser.ml.chat.provider")
    assert got == want, (instance, got)


def test_bundled_libs_are_off_by_default():
    t = _gen()
    for flag in json.loads((ROOT / "pins.json").read_text())["bundled_libs"]:
        assert "+" + flag not in t and re.search(r"\b" + re.escape(flag) + r"\b", t), flag



def test_privacy_badger_is_fetched_pinned_and_forced_like_ublock():
    t = _gen()
    pins = json.loads((ROOT / "pins.json").read_text())
    assert 'POSTERFOX_PB="%s"' % pins["privacy_badger"] in t
    assert "privacy_badger17-${POSTERFOX_PB}.xpi -> posterfox-privacybadger-${POSTERFOX_PB}.xpi" in t
    assert 'jid1-MnnxcxisBPnSXQ@jetpack.xpi' in t
    pol = json.loads((ROOT / "distribution" / "policies.json").read_text())["policies"]["ExtensionSettings"]
    assert pol["jid1-MnnxcxisBPnSXQ@jetpack"]["installation_mode"] == "force_installed"


def test_window_buttons_like_posterchan_windows():
    w = ME.wrapper((FIX / "firefox-files" / "firefox-r1.sh").read_text())
    assert 'export XDG_CONFIG_DIRS="${MOZILLA_FIVE_HOME}/posterchan/xdg' in w
    assert w.index("XDG_CONFIG_DIRS") < w.index("exec ${MOZ_PROGRAM}")
    ini = (ROOT / "distribution" / "xdg" / "gtk-3.0" / "settings.ini").read_text()
    assert "gtk-decoration-layout=:minimize,maximize,close" in ini
    assert "posterchan/xdg/gtk-3.0" in _gen()


def test_private_by_default_no_history_cleared_on_exit_containers_on():
    p = json.loads((ROOT / "distribution" / "policies.json").read_text())["policies"]
    s = p["SanitizeOnShutdown"]
    for k in ("Cache", "Cookies", "Downloads", "FormData", "History", "Sessions", "SiteSettings", "OfflineApps"):
        assert s[k] is True, k
    prefs = p["Preferences"]
    assert prefs["places.history.enabled"]["Value"] is False and prefs["browser.formfill.enable"]["Value"] is False
    assert prefs["privacy.userContext.enabled"]["Value"] is True
    # containers do not work in permanent private browsing, so that mode must stay off
    assert "browser.privatebrowsing.autostart" not in prefs
    assert 'pref("places.history.enabled", false);' in (ROOT / "distribution" / "posterfox-prefs.js").read_text()


def test_our_files_never_land_on_the_browser_binary():
    """The first real build (2026-10-28) compiled for 18 minutes and then died installing: our files went to
    ${MOZILLA_FIVE_HOME}/posterfox, and with --with-app-name=posterfox that path IS the browser executable
    ("install: cannot create directory ... /usr/lib64/posterfox/posterfox: File exists")."""
    import re
    gen = _gen()
    dirs = re.findall(r'insinto "\$\{MOZILLA_FIVE_HOME\}/([^"/]+)', gen)
    assert dirs, "no PosterFox files are installed at all"
    assert "posterfox" not in dirs and "${PN}" not in dirs, dirs


def test_every_file_the_ebuild_reads_from_filesdir_exists():
    """r7 died installing on `${FILESDIR}/icon/${PN}-r3.desktop` (PN=posterfox; the template is firefox-r3.desktop).
    Every literal ${FILESDIR} path the generated ebuild reads must name a file the package ships."""
    import re
    gen = _gen()
    shipped = set()
    for p in (FIX / "firefox-files").rglob("*"):
        if p.is_file():
            shipped.add(str(p.relative_to(FIX / "firefox-files")))
    shipped |= {"posterfox-r1.sh"}           # written by the generator from files/firefox-r1.sh
    refs = set()
    for m in re.finditer(r'\$\{FILESDIR\}"?/([A-Za-z0-9_./${}-]+)', gen):
        path = m.group(1).rstrip('"').replace("${PN}", "posterfox")
        if "posterfox/" in path or "${" in path or path.startswith("posterfox/"):
            continue                          # our own payload (assembled separately) or a computed name
        refs.add(path)
    missing = sorted(r for r in refs if r not in shipped)
    assert not missing, missing
