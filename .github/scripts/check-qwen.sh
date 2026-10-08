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

  # Qwen copies every skill and command file except dotfiles. It may rewrite
  # paths inside them, so compare file names, not content.
  for dir in skills commands; do
    [ -d "$ROOT/$src/$dir" ] || continue
    diff <(cd "$ROOT/$src/$dir" && find . -type f -not -path '*/.*' | sort) \
         <(cd "$ext/$dir" && find . -type f -not -path '*/.*' | sort) \
      || fail "$name: converted $dir have missing or extra files"
  done
done 3< <(plugins)

listing="$($QWEN extensions list 2>&1)"
echo "$listing"
while read -r name src <&3; do
  for skill in $(skills_of "$src"); do
    grep -Eq "(^|[^[:alnum:]_-])$skill([^[:alnum:]_-]|$)" <<<"$listing" || fail "$name: skill $skill not listed by Qwen Code"
  done
  for cmd in $(commands_of "$src"); do
    grep -Eq "(^|[[:space:]])/$cmd([^[:alnum:]_-]|$)" <<<"$listing" || fail "$name: command /$cmd not listed by Qwen Code"
  done
done 3< <(plugins)

echo "Qwen Code: all plugins OK"
