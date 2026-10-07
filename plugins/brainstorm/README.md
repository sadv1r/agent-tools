# brainstorm

A personal fork of the [brainstorm](https://github.com/umputun/cc-thingz/tree/master/plugins/brainstorm)
skill from umputun/cc-thingz. It turns an idea into a design before any code is
written: questions one at a time, two or three approaches with a recommendation,
then the design in short sections, each confirmed before the next.

Forked from upstream plugin version 2.2.2
([`5f947a7`](https://github.com/umputun/cc-thingz/commit/5f947a707caeb60b3c40c83a9ee5c40301fbaf44)).
Changes from upstream:

- No custom rules. The upstream `resolve-rules.sh` loader and the
  `brainstorm-rules.md` files are gone; edit `SKILL.md` instead.

The "Write plan" step hands off to `/planning:make` from the
[planning](https://github.com/umputun/cc-thingz/tree/master/plugins/planning) plugin.

The upstream plugin `brainstorm@umputun-cc-thingz` ships a skill with the same
name. Uninstall it if you install this one, so only one of them triggers.

Upstream is MIT-licensed, © 2026 Umputun.
