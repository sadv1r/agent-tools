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
3. Run `claude plugin validate .` and `claude plugin validate ./plugins/<plugin>`.
4. Bump `version` in the plugin's `plugin.json` whenever you change the plugin.
   Installed copies only update when the version changes.

To try a local checkout before pushing, run
`claude plugin marketplace add ./` (Claude Code) or
`qwen extensions install ./:<plugin>` (Qwen Code).
