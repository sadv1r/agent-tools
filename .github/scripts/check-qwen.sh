#!/usr/bin/env bash
# Installs each plugin into a throwaway Qwen Code home through the Claude
# marketplace converter, and checks the converted extension.
# Without a global `qwen`, run: QWEN="npx -y @qwen-code/qwen-code@latest" .github/scripts/check-qwen.sh
source "$(dirname "$0")/lib.sh"
QWEN="${QWEN:-qwen}"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# Qwen leaves a plugin<hash>/ copy inside a local marketplace, so install from a copy.
cp -R "$ROOT" "$tmp/marketplace"
export npm_config_cache="${npm_config_cache:-$HOME/.npm}"
export HOME="$tmp/home"
mkdir -p "$HOME"

while read -r name src <&3; do
  echo "== $name"
  $QWEN extensions install "$tmp/marketplace:$name" --consent

  ext="$HOME/.qwen/extensions/$name"
  [ -f "$ext/qwen-extension.json" ] || fail "$name: no qwen-extension.json after install"
  want="$(json_field "$ROOT/$src/.claude-plugin/plugin.json" version)"
  got="$(json_field "$ext/qwen-extension.json" version)"
  [ "$got" = "$want" ] || fail "$name: converted version is '$got', expected '$want'"

  # The converter copies skills verbatim (dotfiles excluded).
  if [ -d "$ROOT/$src/skills" ]; then
    diff -r -x '.*' "$ROOT/$src/skills" "$ext/skills" || fail "$name: converted skills differ from the source"
  fi
done 3< <(plugins)

listing="$($QWEN extensions list 2>&1)"
echo "$listing"
while read -r name src <&3; do
  for skill in $(skills_of "$src"); do
    grep -Eq "(^|[^[:alnum:]_-])$skill([^[:alnum:]_-]|$)" <<<"$listing" || fail "$name: skill $skill not listed by Qwen Code"
  done
done 3< <(plugins)

echo "Qwen Code: all plugins OK"
