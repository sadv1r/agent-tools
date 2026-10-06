# Shared helpers for the check scripts. Source this file, don't run it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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

# Prints the skill names a plugin ships: every skills/<name>/SKILL.md under it.
skills_of() {
  local f
  for f in "$ROOT/$1"/skills/*/SKILL.md; do
    [ -e "$f" ] && basename "$(dirname "$f")"
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
