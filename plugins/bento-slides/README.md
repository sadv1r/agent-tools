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

## Updating from bento.page

Every Monday the `bento-upstream` workflow compares the bundled files with
bento.page. If anything differs, it opens an issue labeled `bento-upstream`
that lists the changes. Later runs update that same issue instead of opening
new ones. `upstream-skill.sha256` is the checksum of the upstream SKILL.md
this copy was made from. The weekly check uses it to notice when upstream
changes that file.

To update, run from this directory:

```bash
S=skills/bento-slides
curl -fsSL https://bento.page/agents.md -o $S/references/agents.md
curl -fsSL https://bento.page/releases/slides/Bento_Slides.bento.html -o $S/assets/Bento_Slides.bento.html
# Repeat for each new or changed template the issue lists, and delete the ones it says are gone:
curl -fsSL https://bento.page/gallery/<name>.bento.html -o $S/assets/templates/<name>.bento.html
```

If the issue says `SKILL.md` changed, port the upstream changes it shows into
`skills/bento-slides/SKILL.md`. Keep the local edits that point to the bundled
files instead of downloading them. Then record the upstream version you
ported:

```bash
curl -fsSL https://bento.page/skills/bento-slides/SKILL.md | shasum -a 256 | cut -d' ' -f1 > upstream-skill.sha256
```

Finally, bump `version` in `.claude-plugin/plugin.json` and close the issue.
