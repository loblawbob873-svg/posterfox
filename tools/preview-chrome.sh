#!/bin/bash
# See PosterFox's window chrome without building PosterFox: a stock Firefox in a HEADLESS Wayfire, with a throwaway
# profile whose userChrome.css is distribution/posterfox-chrome.css and the signed cyberpunk theme, screenshotted.
#
#   tools/preview-chrome.sh OUT.png [URL] [WIDTHxHEIGHT]
#
# Needs wayfire, grim and a firefox (firefox-bin is what PosterChanOS ships). Nothing outside a temp dir is touched.
set -euo pipefail
OUT=${1:?OUT.png}; URL=${2:-about:blank}; SIZE=${3:-1400x860}
HERE=$(cd "$(dirname "$0")/.." && pwd)
FF=$(command -v firefox-bin || command -v firefox)
THEME=$(ls /usr/share/posterchanos/firefox/posterchan-cyberpunk-*.xpi 2>/dev/null | tail -1 || true)
T=$(mktemp -d); trap 'kill $(jobs -p) 2>/dev/null; rm -rf "$T"' EXIT
export XDG_RUNTIME_DIR=$T/run; mkdir -p "$XDG_RUNTIME_DIR"; chmod 700 "$XDG_RUNTIME_DIR"
printf '[core]\nplugins = \nxwayland = true\n[output:HEADLESS-1]\nmode = %s@60000\n' "$SIZE" > "$T/wayfire.ini"
WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1 wayfire -c "$T/wayfire.ini" >"$T/wf.log" 2>&1 &
for _ in $(seq 50); do W=$(ls "$XDG_RUNTIME_DIR" 2>/dev/null | grep -m1 '^wayland-[0-9]$' || true); [ -n "$W" ] && break; sleep .2; done
export WAYLAND_DISPLAY=${W:?wayfire did not start: $(tail -3 "$T/wf.log")}
P=$T/profile; mkdir -p "$P/chrome" "$P/extensions"
cp "$HERE/distribution/posterfox-chrome.css" "$P/chrome/userChrome.css"
[ -n "$THEME" ] && cp "$THEME" "$P/extensions/cyberpunk-theme@poster.place.xpi"
cat > "$P/user.js" <<EOF
user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);
user_pref("extensions.autoDisableScopes", 0);
user_pref("extensions.activeThemeID", "cyberpunk-theme@poster.place");
user_pref("browser.tabs.inTitlebar", 1);
user_pref("browser.aboutwelcome.enabled", false);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);
user_pref("browser.shell.checkDefaultBrowser", false);
EOF
# Wayland if this machine's GTK has it, else X11 through Xwayland (a server's GTK often has no Wayland backend).
for _ in $(seq 50); do X=$(ls /tmp/.X11-unix 2>/dev/null | sed -n 's/^X//p' | sort -n | tail -1); grep -q "DISPLAY\|Xwayland\|xwayland" "$T/wf.log" && break; sleep .2; done
XD=$(grep -o 'DISPLAY=:[0-9]*\|display :[0-9]*\|:[0-9]\+' "$T/wf.log" | grep -o ':[0-9]*' | tail -1)
# The theme add-on is NOT shown here (a sideloaded theme does not activate in a fresh profile); the stylesheet
# carries the cyberpunk colours itself, which is exactly what this previews.
# GTK_THEME/button layout: a bare server has no desktop settings, and Firefox then draws no min/max/close at all.
run_ff() { env -u MOZ_HEADLESS DISPLAY="${XD:-:0}" GTK_THEME=Adwaita:dark \
  "$FF" --no-remote --profile "$P" --new-window "$URL" >>"$T/ff.log" 2>&1 & echo $!; }
mkdir -p "$T/xdg/gtk-3.0"; printf '[Settings]\ngtk-decoration-layout=:minimize,maximize,close\n' > "$T/xdg/gtk-3.0/settings.ini"
export XDG_CONFIG_HOME="$T/xdg"
run_ff >/dev/null
sleep "${PREVIEW_WAIT:-12}"
grim "$OUT"
[ -n "${PREVIEW_DEBUG:-}" ] && { echo "--- firefox"; tail -15 "$T/ff.log"; echo "--- wayfire"; tail -8 "$T/wf.log"; }
echo "$OUT"
