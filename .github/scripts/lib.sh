# Shared helpers for the check scripts. Source this file, don't run it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# Used by the scripts that source this file.
# shellcheck disable=SC2034
MARKETPLACE="$(node -p 'require(process.argv[1]).name' "$ROOT/.claude-plugin/marketplace.json")"

# Prints "<name> <dir>" for every marketplace entry with a relative-path source.
plugins() {
  node -e '
    for (const p of require(process.argv[1]).plugins)
      if (typeof p.source === "string") console.log(p.name, p.source.replace(/^\.\//, ""));
  ' "$ROOT/.claude-plugin/marketplace.json"
}

# json_field <file> <field> prints the field, or nothing when it is missing.
json_field() {
  node -p 'require(process.argv[1])[process.argv[2]] ?? ""' "$1" "$2"
}

# entry_field <plugin> <field> prints the field of the plugin's marketplace entry,
# or nothing when it is missing.
entry_field() {
  node -p '
    require(process.argv[1]).plugins.find(p => p.name === process.argv[2])?.[process.argv[3]] ?? ""
  ' "$ROOT/.claude-plugin/marketplace.json" "$1" "$2"
}

# Prints the skill names a plugin ships: every skills/<name>/SKILL.md under it.
skills_of() {
  local f
  for f in "$ROOT/$1"/skills/*/SKILL.md; do
    [ -e "$f" ] && basename "$(dirname "$f")"
  done
  return 0
}

# Prints the slash commands a plugin ships: every commands/<name>.md under it.
commands_of() {
  local f
  for f in "$ROOT/$1"/commands/*.md; do
    [ -e "$f" ] && basename "$f" .md
  done
  return 0
}

error() {
  if [ -n "${GITHUB_ACTIONS:-}" ]; then echo "::error::$*"; else echo "error: $*"; fi >&2
}

fail() {
  error "$@"
  exit 1
}
