#!/usr/bin/env bash
# Checks whether bento.page has published files that differ from the ones
# bundled in plugins/bento-slides, and writes a markdown report of the changes.
# Usage: scripts/check-bento-upstream.sh [report-file]
# Under GitHub Actions it also sets the output `changed` to true or false.
source "$(dirname "$0")/lib.sh"
report="${1:-/dev/stdout}"

SITE=https://bento.page
PLUGIN="$ROOT/plugins/bento-slides"
SKILL="$PLUGIN/skills/bento-slides"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
get() { curl -fsSL --retry 3 -o "$2" "$SITE/$1"; }
guide_version() { grep -oE 'Guide version `[^`]+`' "$1" | tr -d '`' | awk '{print $3}'; }

changes=""
add() { changes+="- $1"$'\n'; }

get agents.md "$tmp/agents.md"
cmp -s "$tmp/agents.md" "$SKILL/references/agents.md" \
  || add "\`references/agents.md\`: guide $(guide_version "$SKILL/references/agents.md") → $(guide_version "$tmp/agents.md")"

get releases/slides/Bento_Slides.bento.html "$tmp/app.html"
cmp -s "$tmp/app.html" "$SKILL/assets/Bento_Slides.bento.html" \
  || add "\`assets/Bento_Slides.bento.html\`: new app release"

get "" "$tmp/index.html"
templates="$(grep -oE '/gallery/[a-z0-9-]+\.bento\.html' "$tmp/index.html" | sort -u | xargs -n1 basename)"
for t in $templates; do
  if [ ! -f "$SKILL/assets/templates/$t" ]; then
    add "\`assets/templates/$t\`: new template"
  else
    get "gallery/$t" "$tmp/$t"
    cmp -s "$tmp/$t" "$SKILL/assets/templates/$t" || add "\`assets/templates/$t\`: changed"
  fi
done
for f in "$SKILL"/assets/templates/*.bento.html; do
  t="$(basename "$f")"
  grep -qxF "$t" <<<"$templates" || add "\`assets/templates/$t\`: no longer on bento.page"
done

# The local SKILL.md is edited for offline use, so compare upstream with the
# checksum of the upstream version it was made from.
get skills/bento-slides/SKILL.md "$tmp/SKILL.md"
skill_changed=false
if [ "$(shasum -a 256 "$tmp/SKILL.md" | cut -d' ' -f1)" != "$(tr -d '[:space:]' < "$PLUGIN/upstream-skill.sha256")" ]; then
  skill_changed=true
  add "\`SKILL.md\`: upstream changed (diff below)"
fi

if [ -z "$changes" ]; then
  echo "bento-slides matches $SITE"
  if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "changed=false" >> "$GITHUB_OUTPUT"; fi
  exit 0
fi

{
  echo "bento.page has files that differ from the copies bundled in \`plugins/bento-slides/skills/bento-slides\`:"
  echo
  printf '%s' "$changes"
  echo
  echo "To update, follow **Updating from bento.page** in \`plugins/bento-slides/README.md\`."
  if $skill_changed; then
    echo
    echo "<details><summary>Diff from the local SKILL.md to the new upstream SKILL.md</summary>"
    echo
    echo "The local file's offline edits show up here too. Port only the other changes."
    echo
    echo '````diff'
    diff -u -L local/SKILL.md -L upstream/SKILL.md "$SKILL/SKILL.md" "$tmp/SKILL.md" || true
    echo '````'
    echo
    echo "</details>"
  fi
} > "$report"

if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "changed=true" >> "$GITHUB_OUTPUT"; fi
echo "bento.page has updates for bento-slides"
