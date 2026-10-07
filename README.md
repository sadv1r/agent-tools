# agent-tools

Personal plugin marketplace for **Claude Code** and **Qwen Code**. The plugins
use the Claude Code layout (`.claude-plugin/marketplace.json`). Qwen Code
installs from that layout too and converts each plugin into a Qwen extension.

| Plugin | What it does |
|---|---|
| [`offline-bento-slides`](plugins/offline-bento-slides) | Create and edit [Bento](https://bento.page) `.bento.html` slide decks fully offline, using the bundled app, agent guide and gallery templates |
| [`workflow`](plugins/workflow) | `/retry` resumes work cut off by an interruption; the `backlog` skill keeps deferred work in `docs/backlog/`, one file per item |

## Install

### Claude Code

```text
/plugin marketplace add sadv1r/agent-tools
/plugin install offline-bento-slides@sadv1r-agent-tools
/plugin install workflow@sadv1r-agent-tools
```

Updates arrive with `/plugin marketplace update sadv1r-agent-tools`. You can also
turn on auto-update under `/plugin` → **Marketplaces** → `sadv1r-agent-tools`.

### Qwen Code

```bash
qwen extensions install sadv1r/agent-tools:offline-bento-slides
qwen extensions install sadv1r/agent-tools:workflow
```

To update later, run `qwen extensions update <plugin>`.

To install from a zip instead,
[download the repository as a zip](https://github.com/sadv1r/agent-tools/archive/refs/heads/main.zip)
(on GitHub: **Code** → **Download ZIP**). You don't need to extract it. In a
Qwen Code session, install each plugin from the zip:

```text
/extensions install ~/Downloads/agent-tools-main.zip:offline-bento-slides
/extensions install ~/Downloads/agent-tools-main.zip:workflow
```

To update a zip install, download a new zip to the same path. Then, in a Qwen
Code session, open `/extensions manage`, select the plugin and choose
**Mark for Update**. Qwen reports that an update is available; choose
**Update Now**.

## Adding a plugin

```text
plugins/<plugin>/
├── .claude-plugin/plugin.json      # name, version, description, author
├── skills/<skill>/SKILL.md         # plus any references/, assets/, scripts/
└── commands/<command>.md           # slash commands
```

1. Create the directory above. The `name` in `plugin.json` must match the
   folder name.
2. Add an entry to `.claude-plugin/marketplace.json` with
   `"source": "./plugins/<plugin>"` and the same `name`.
3. Run `.github/scripts/check-claude.sh` (see [Checks](#checks)).
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
| `.github/scripts/check-claude.sh` | `claude plugin validate --strict` passes for the marketplace and each plugin; every `plugins/<name>/` has a marketplace entry with `"source": "./plugins/<name>"`; manifest names and descriptions match, and `version` is set only in `plugin.json`; each plugin installs and all of its skills and commands load |
| `.github/scripts/check-qwen.sh` | Each plugin installs in Qwen Code through its Claude converter; the version carries over and the skills and commands arrive intact |
| `.github/scripts/check-version-bump.sh <base>` | Every plugin whose files changed since `<base>` has a new `version` |
| `shellcheck -x -s bash .github/scripts/*.sh` | The check scripts themselves lint clean |

A second workflow, `bento-upstream`, runs every Monday and on every push to
`main` that changes the offline-bento-slides plugin. It opens an issue
whenever bento.page publishes newer files than the ones bundled in the
plugin, and closes it once they match again. See
[plugins/offline-bento-slides](plugins/offline-bento-slides/README.md#updating-from-bentopage).

The check scripts run locally too. Each one installs into a throwaway config,
so your own setup isn't touched:

```bash
.github/scripts/check-claude.sh
QWEN="npx -y @qwen-code/qwen-code@latest" .github/scripts/check-qwen.sh   # if qwen isn't installed
.github/scripts/check-version-bump.sh origin/main
```
