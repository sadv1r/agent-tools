# bento-slides

An offline copy of the upstream [bento-slides](https://bento.page/skills/bento-slides/SKILL.md)
skill. Everything the upstream skill downloads is bundled here, so creating a
deck needs no network access.

| File | Upstream source |
|---|---|
| `skills/bento-slides/SKILL.md` | `https://bento.page/skills/bento-slides/SKILL.md`, with the download steps changed to use the bundled files |
| `skills/bento-slides/references/agents.md` | `https://bento.page/agents.md`, verbatim. Its first lines give the guide version |
| `skills/bento-slides/assets/Bento_Slides.bento.html` | `https://bento.page/releases/slides/Bento_Slides.bento.html`, verbatim |
| `skills/bento-slides/assets/templates/*.bento.html` | Every gallery deck linked from `https://bento.page`, verbatim |

Bento is MIT-licensed, © 2026 The Bento authors.
Each `.bento.html` file carries its own license notice. The fonts embedded in
the templates (Fraunces, Instrument Sans) are under the OFL.

The upstream plugin `bento-slides@bento` uses the same plugin and skill name.
Uninstall it if you install this one, so only one of them triggers.

## Staying in sync with bento.page

The `update-bento` workflow runs every Monday and can also be started by hand.
It runs `scripts/update-bento.sh` from the repo root, which works the same way
locally:

- `agents.md`, the app and the gallery decks are downloaded again and
  replaced verbatim. Templates that are no longer on the site are removed.
- If upstream `SKILL.md` changed, the change is merged into the local
  `SKILL.md` with a 3-way merge. The merge base is the pristine upstream copy
  in `upstream/bento-slides/SKILL.md`. If the change touches the lines that
  were edited for offline use, nothing is merged, and the PR says what to
  port by hand.
- If anything changed, the plugin version gets a patch bump and a pull
  request opens (or updates) on the `update/bento-slides` branch.

PRs opened by the workflow's built-in token don't start the `check` workflow
by themselves. The PR shows **Approve workflows to run**, and one click runs
the checks. To skip that click, add a fine-grained personal access token as
the repository secret `AGENT_TOOLS_PR_TOKEN`. It needs Contents and Pull
requests read/write access on this repo only. The workflow uses it when it is
present.

If a new upstream line mentions a URL or a download, the PR quotes it, so you
can make sure the skill still works offline.
