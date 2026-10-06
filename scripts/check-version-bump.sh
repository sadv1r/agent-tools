#!/usr/bin/env bash
# Fails when a plugin's files changed since <base> but its plugin.json version
# did not. Installed copies only update when the version changes.
# Locally: scripts/check-version-bump.sh origin/main
source "$(dirname "$0")/lib.sh"
base="${1:?usage: check-version-bump.sh <base-commit>}"

# A push that creates a branch has an all-zero "before" commit.
if [[ "$base" =~ ^0+$ ]] || ! git -C "$ROOT" cat-file -e "$base^{commit}" 2>/dev/null; then
  echo "No usable base commit ($base), skipping."
  exit 0
fi

status=0
while read -r name src <&3; do
  # Compares against the working tree, so it also works before committing.
  if git -C "$ROOT" diff --quiet "$base" -- "$src"; then
    echo "$name: unchanged"
    continue
  fi

  manifest="$src/.claude-plugin/plugin.json"
  if ! git -C "$ROOT" cat-file -e "$base:$manifest" 2>/dev/null; then
    echo "$name: new plugin"
    continue
  fi

  old="$(git -C "$ROOT" show "$base:$manifest" | node -p 'JSON.parse(require("fs").readFileSync(0, "utf8")).version ?? ""')"
  new="$(json_field "$ROOT/$manifest" version)"
  if [ "$old" = "$new" ]; then
    error "$name changed but its version is still '$new'. Bump version in $manifest."
    status=1
  else
    echo "$name: $old -> $new"
  fi
done 3< <(plugins)

exit "$status"
