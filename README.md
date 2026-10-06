# agent-tools

Personal plugin marketplace for **Claude Code** and **Qwen Code**. The plugins
use the Claude Code layout (`.claude-plugin/marketplace.json`). Qwen Code
installs from that layout too and converts each plugin into a Qwen extension.

| Plugin | What it does |
|---|---|
| [`bento-slides`](plugins/bento-slides) | Create and edit [Bento](https://bento.page) `.bento.html` slide decks fully offline, using the bundled app, agent guide and gallery templates |

## Install

The repository is private, so git on your machine must already be able to
read it. For HTTPS, run `gh auth login` and then `gh auth setup-git`. For SSH,
use a key that is loaded in `ssh-agent`.

### Claude Code

```text
/plugin marketplace add sadv1r/agent-tools
/plugin install bento-slides@agent-tools
```

Updates arrive with `/plugin marketplace update agent-tools`. You can also
turn on auto-update under `/plugin` → **Marketplaces** → `agent-tools`.

### Qwen Code

Qwen reads `marketplace.json` through the GitHub API, which needs a token for
a private repository:

```bash
export GITHUB_TOKEN="$(gh auth token)"
qwen extensions install sadv1r/agent-tools:bento-slides
```

To update later, run `qwen extensions update bento-slides`.

## Adding a plugin

```text
plugins/<plugin>/
├── .claude-plugin/plugin.json      # name, version, description, author
└── skills/<skill>/SKILL.md         # plus any references/, assets/, scripts/
```

1. Create the directory above. The `name` in `plugin.json` must match the
   folder name.
2. Add an entry to `.claude-plugin/marketplace.json` with
   `"source": "./plugins/<plugin>"` and the same `name`.
3. Run `scripts/check-claude.sh` (see [Checks](#checks)).
4. Bump `version` in the plugin's `plugin.json` whenever you change the plugin.
   Installed copies only update when the version changes.

To try a local checkout before pushing, run
`claude plugin marketplace add ./` (Claude Code) or
`qwen extensions install ./:<plugin>` (Qwen Code).

## Checks

`.github/workflows/check.yml` runs on every push to `main`, on pull requests,
and weekly against the latest releases of both CLIs. No API keys are needed.

| Script | What it checks |
|---|---|
| `scripts/check-claude.sh` | `claude plugin validate --strict` passes for the marketplace and each plugin; manifest names match; each plugin installs and all of its skills load |
| `scripts/check-qwen.sh` | Each plugin installs in Qwen Code through its Claude converter; the version carries over and the skills arrive intact |
| `scripts/check-version-bump.sh <base>` | Every plugin whose files changed since `<base>` has a new `version` |

A second workflow, `bento-upstream`, runs every Monday. It opens an issue
whenever bento.page publishes newer files than the ones bundled in the
bento-slides plugin. See
[plugins/bento-slides](plugins/bento-slides/README.md#updating-from-bentopage).

The check scripts run locally too. Each one installs into a throwaway config,
so your own setup isn't touched:

```bash
scripts/check-claude.sh
QWEN="npx -y @qwen-code/qwen-code@latest" scripts/check-qwen.sh   # if qwen isn't installed
scripts/check-version-bump.sh origin/main
```
