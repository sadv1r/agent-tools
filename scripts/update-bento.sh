#!/usr/bin/env bash
# Refreshes plugins/bento-slides from the live bento.page site:
# - agents.md, the app and the gallery templates are copied verbatim;
# - an upstream SKILL.md change is 3-way merged into the local offline edits,
#   with upstream/bento-slides/SKILL.md as the merge base;
# - the plugin version gets a patch bump when anything changed.
# Usage: scripts/update-bento.sh [pr-body-file]
# Under GitHub Actions it also sets the outputs `changed` and `title`.
source "$(dirname "$0")/lib.sh"
body="${1:-/dev/stdout}"

SITE=https://bento.page
PLUGIN="plugins/bento-slides"
SKILL="$ROOT/$PLUGIN/skills/bento-slides"
BASE_SKILL="$ROOT/upstream/bento-slides/SKILL.md"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
get() { curl -fsSL --retry 3 -o "$2" "$SITE/$1"; }
guide_version() { grep -oE 'Guide version `[^`]+`' "$1" | tr -d '`' | awk '{print $3}'; }

get agents.md "$tmp/agents.md"
get releases/slides/Bento_Slides.bento.html "$tmp/app.html"
get skills/bento-slides/SKILL.md "$tmp/SKILL.md"
get "" "$tmp/index.html"
mkdir "$tmp/templates"
templates="$(grep -oE '/gallery/[a-z0-9-]+\.bento\.html' "$tmp/index.html" | sort -u | xargs -n1 basename)"
[ -n "$templates" ] || fail "no gallery templates linked from $SITE"
for t in $templates; do get "gallery/$t" "$tmp/templates/$t"; done

# Sanity-check the downloads before anything is written.
head -1 "$tmp/agents.md" | grep -q '^# bento/slides' || fail "agents.md is not the bento/slides guide"
grep -q '<script type="application/bento+json" id="bento-doc"></script>' "$tmp/app.html" \
  || fail "the app has no empty #bento-doc block, which the skill relies on"
for t in "$tmp"/templates/*; do
  grep -q 'id="bento-doc"' "$t" || fail "$(basename "$t") has no #bento-doc block"
done
grep -q '^name: bento-slides$' "$tmp/SKILL.md" || fail "SKILL.md is not the bento-slides skill"

old_guide="$(guide_version "$SKILL/references/agents.md")"
new_guide="$(guide_version "$tmp/agents.md")"
cp "$tmp/agents.md" "$SKILL/references/agents.md"
cp "$tmp/app.html" "$SKILL/assets/Bento_Slides.bento.html"
rm -f "$SKILL"/assets/templates/*.bento.html
cp "$tmp"/templates/*.bento.html "$SKILL/assets/templates/"

skill_note=""
if ! cmp -s "$tmp/SKILL.md" "$BASE_SKILL"; then
  # Upstream lines that mention the network need a look: the skill must stay offline.
  network="$(diff "$BASE_SKILL" "$tmp/SKILL.md" | sed -n 's/^> //p' \
    | grep -Ei 'https?://|curl|wget|iwr|download|fetch' || true)"
  cp "$SKILL/SKILL.md" "$tmp/merged.md"
  if git merge-file -q -L local -L "previous upstream" -L "new upstream" \
       "$tmp/merged.md" "$BASE_SKILL" "$tmp/SKILL.md"; then
    cp "$tmp/merged.md" "$SKILL/SKILL.md"
    skill_note="Upstream SKILL.md changed and was merged into the local SKILL.md automatically. Check the merge."
  else
    skill_note="Upstream SKILL.md changed in lines the local offline edits also touch, so it was **not merged**. Port the change shown in \`upstream/bento-slides/SKILL.md\` into \`$PLUGIN/skills/bento-slides/SKILL.md\` on this branch before merging."
  fi
  if [ -n "$network" ]; then
    skill_note+=$'\n\nNew upstream lines mention downloads or URLs. Make sure the skill still works offline:\n\n```text\n'"$network"$'\n```'
  fi
  cp "$tmp/SKILL.md" "$BASE_SKILL"
fi

changes="$(git -C "$ROOT" status --porcelain -- "$PLUGIN" upstream/bento-slides)"
if [ -z "$changes" ]; then
  echo "bento-slides is up to date with $SITE"
  [ -n "${GITHUB_OUTPUT:-}" ] && echo "changed=false" >> "$GITHUB_OUTPUT"
  exit 0
fi

manifest="$ROOT/$PLUGIN/.claude-plugin/plugin.json"
old_version="$(json_field "$manifest" version)"
# Edit the version string in place so the rest of the file keeps its formatting.
node -e '
  const fs = require("fs"), f = process.argv[1];
  fs.writeFileSync(f, fs.readFileSync(f, "utf8").replace(
    /("version"\s*:\s*")(\d+)\.(\d+)\.(\d+)"/, (_, k, a, b, c) => `${k}${a}.${b}.${Number(c) + 1}"`));
' "$manifest"
new_version="$(json_field "$manifest" version)"

title="bento-slides: sync with bento.page (guide $new_guide)"
{
  echo "Weekly sync of the files bundled in \`$PLUGIN\` with $SITE."
  echo
  echo "- Plugin version: $old_version → $new_version"
  if [ "$old_guide" = "$new_guide" ]; then
    echo "- Agent guide (\`agents.md\`): $new_guide, unchanged"
  else
    echo "- Agent guide (\`agents.md\`): $old_guide → $new_guide"
  fi
  echo
  echo "Changed files:"
  echo
  echo '```text'
  echo "$changes"
  echo '```'
  if [ -n "$skill_note" ]; then
    echo
    echo "$skill_note"
  fi
  echo
  echo "Before merging, open a deck made with the new app and page through it."
} > "$body"

if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "changed=true" >> "$GITHUB_OUTPUT"
  echo "title=$title" >> "$GITHUB_OUTPUT"
fi
echo "$title"
