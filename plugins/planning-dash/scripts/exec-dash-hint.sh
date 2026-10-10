#!/bin/sh
# Claude Code PostToolUse hook for Bash (see hooks/hooks.json): when /planning:exec initializes its
# progress file, show a short hint on the agterm session with the key that opens the live dashboard.
# Only the command that ran counts, not its output: a tool result quoting the script's path (a grep
# over the plugin files, say) must not trigger the hint. Outside agterm, or without a keymap binding
# for exec-dash.py, it does nothing.
[ -n "$AGTERM_SESSION_ID" ] && [ -n "$AGTERM_SOCKET" ] || exit 0
py=$(command -v python3 || echo /usr/bin/python3)
"$py" -c '
import json, sys
try:
    command = (json.load(sys.stdin).get("tool_input") or {}).get("command") or ""
except ValueError:
    command = ""
sys.exit(0 if "skills/exec/scripts/init-progress.sh" in command else 1)
' || exit 0

# the chord bound to the dashboard: `command "Exec dashboard" cmd+shift+e ... exec-dash.py ...`
keymap="${XDG_CONFIG_HOME:-$HOME/.config}/agterm/keymap.conf"
chord=$(sed -n 's/^command "[^"]*" *\([a-zA-Z0-9+>]*\) .*exec-dash\.py.*/\1/p' "$keymap" 2>/dev/null | head -1)
[ -n "$chord" ] || exit 0
keys=$(printf '%s' "$chord" | sed 's/cmd+/⌘/g; s/shift+/⇧/g; s/ctrl+/⌃/g; s/opt+/⌥/g; s/alt+/⌥/g' | tr 'a-z' 'A-Z')

ctl=$(command -v agtermctl || echo /opt/homebrew/bin/agtermctl)
"$ctl" session hud "Exec dashboard: press $keys" \
  --detail "Live tasks, status and timings · $keys again to close" \
  --position top-right --hide-after 60 \
  --target "$AGTERM_SESSION_ID" --socket "$AGTERM_SOCKET" >/dev/null 2>&1 || true
