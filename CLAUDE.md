# agent-tools

A plugin marketplace for Claude Code and Qwen Code. See README.md for the layout.

- Each plugin lives in `plugins/<name>/` and has an entry in `.claude-plugin/marketplace.json`. Both must use the same `name`, and the entry's `source` must be `./plugins/<name>`.
- Set `version` only in the plugin's `plugin.json`, never in the marketplace entry. Bump it on every change to a plugin, or installed copies won't update. Qwen Code needs a version too.
- Before pushing, run `scripts/check-claude.sh` and `scripts/check-version-bump.sh origin/main`. CI also runs `scripts/check-qwen.sh`.
- Upstream files bundled in `plugins/bento-slides` (`references/agents.md`, `assets/`) are verbatim snapshots. Don't edit them; refresh them as described in that plugin's README.
