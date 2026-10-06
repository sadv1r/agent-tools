# workflow

Commands and skills for steering a session and keeping track of deferred work.

| Command or skill | What it does |
|---|---|
| `/retry` | Resumes whatever was in progress before an interruption (manual stop, network loss, error, crash). It checks the real state of any tool call that was cut off, won't repeat side effects such as commits or pushes without confirming they didn't already happen, and re-asks any pending question |
| `backlog` skill | Keeps a repo's deferred work in `docs/backlog/`, one Markdown file per item, triaged as `worth: yes`, `later` or `no`. Lists and verifies items, walks them one at a time to fix or drop (`/workflow:backlog --all` or `/workflow:backlog <slug>`), and offers to file new ones when a review turns up work that isn't being done now. A fixed item is deleted with `git rm` in the commit that fixes it |

In Claude Code the command is also available as `/workflow:retry`.

The `backlog` skill is a personal fork of the
[backlog](https://github.com/umputun/cc-thingz/tree/master/plugins/workflow/skills/backlog)
skill from umputun/cc-thingz, forked from upstream workflow plugin version 1.3.0
([`b8f4a23`](https://github.com/umputun/cc-thingz/commit/b8f4a231bbe84bf645ebb4908f9cdc962e2b15e3)).
The only change from upstream is one pronoun made gender-neutral.

Upstream is MIT-licensed, © 2026 Umputun.
