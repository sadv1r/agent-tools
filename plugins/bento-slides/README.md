# bento-slides

An offline copy of the upstream [bento-slides](https://bento.page/skills/bento-slides/SKILL.md)
skill. Everything the upstream skill downloads is bundled here, so creating a
deck needs no network access.

| File | Upstream source |
|---|---|
| `skills/bento-slides/SKILL.md` | `https://bento.page/skills/bento-slides/SKILL.md`, with the download steps changed to use the bundled files |
| `skills/bento-slides/references/agents.md` | `https://bento.page/agents.md` (guide v1.2.6), verbatim |
| `skills/bento-slides/assets/Bento_Slides.bento.html` | `https://bento.page/releases/slides/Bento_Slides.bento.html`, verbatim |
| `skills/bento-slides/assets/templates/*.bento.html` | `https://bento.page/gallery/<name>.bento.html`, verbatim |

Snapshot taken on 2026-10-06. Bento is MIT-licensed, © 2026 The Bento authors.
Each `.bento.html` file carries its own license notice. The fonts embedded in
the templates (Fraunces, Instrument Sans) are under the OFL.

The upstream plugin `bento-slides@bento` uses the same plugin and skill name.
Uninstall it if you install this one, so only one of them triggers.

## Refreshing the snapshot

From this directory:

```bash
S=skills/bento-slides
curl -fsSL https://bento.page/agents.md -o $S/references/agents.md
curl -fsSL https://bento.page/releases/slides/Bento_Slides.bento.html -o $S/assets/Bento_Slides.bento.html
for t in signal-editorial-type terra-premium-product orbital-dark-immersive picnic-playful; do
  curl -fsSL https://bento.page/gallery/$t.bento.html -o $S/assets/templates/$t.bento.html
done
```

After refreshing, compare `https://bento.page/skills/bento-slides/SKILL.md`
with the local `SKILL.md`. Port any upstream changes, keeping the local edits
that replace downloads. Then update the snapshot date above and bump `version`
in `.claude-plugin/plugin.json`.
