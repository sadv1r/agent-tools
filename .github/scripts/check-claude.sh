#!/usr/bin/env bash
# Validates the marketplace and every plugin with Claude Code, then installs each
# plugin into a throwaway config and checks that all of its skills and commands load.
source "$(dirname "$0")/lib.sh"

claude plugin validate --strict "$ROOT"

CLAUDE_CONFIG_DIR="$(mktemp -d)"
export CLAUDE_CONFIG_DIR
trap 'rm -rf "$CLAUDE_CONFIG_DIR"' EXIT
claude plugin marketplace add "$ROOT"

while read -r name src <&3; do
  echo "== $name"
  claude plugin validate --strict "$ROOT/$src"

  manifest="$ROOT/$src/.claude-plugin/plugin.json"
  [ "$(json_field "$manifest" name)" = "$name" ] || fail "$name: plugin.json name differs from the marketplace entry"
  [ "$(json_field "$manifest" description)" = "$(entry_field "$name" description)" ] || fail "$name: plugin.json description differs from the marketplace entry"
  [ -n "$(json_field "$manifest" version)" ] || fail "$name: plugin.json has no version (Qwen Code needs one, and updates key off it)"

  claude plugin install "$name@$MARKETPLACE"
  details="$(claude plugin details "$name")"
  echo "$details"

  # `details` prints "Skills (N)  a, b" followed by the next section, "Agents (N)".
  # Commands are listed there too.
  loaded="$(awk '/^ *Skills \(/ { f = 1 } /^ *Agents \(/ { f = 0 } f' <<<"$details")"
  expected="$( { skills_of "$src"; commands_of "$src"; } | wc -l | tr -d ' ')"
  grep -q "Skills ($expected)" <<<"$loaded" || fail "$name: expected $expected skill(s) and command(s), got: $loaded"
  for skill in $(skills_of "$src") $(commands_of "$src"); do
    grep -Eq "(^|[^[:alnum:]_-])$skill([^[:alnum:]_-]|$)" <<<"$loaded" || fail "$name: $skill did not load"
  done
done 3< <(plugins)

echo "Claude Code: all plugins OK"
