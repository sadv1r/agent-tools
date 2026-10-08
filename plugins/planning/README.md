# planning

A personal fork of the [planning](https://github.com/umputun/cc-thingz/tree/master/plugins/planning)
plugin from umputun/cc-thingz. `/planning:make` writes a structured
implementation plan to `docs/plans/`. The `exec` skill runs it task by task,
each in a fresh subagent, then reviews the result and finalizes the branch.
See [references/usage.md](references/usage.md).

Forked from upstream plugin version 3.10.3
([`d407561`](https://github.com/umputun/cc-thingz/commit/d407561bca8dbb42d5eade428a048f64525c710c)).

The upstream plugin `planning@umputun-cc-thingz` has the same name. Uninstall
it if you install this one, so only one of them triggers.

Upstream is MIT-licensed, © 2026 Umputun.
