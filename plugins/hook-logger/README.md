# hook-logger

Logs the payload of every Claude Code hook event to a JSONL file, so you can
see exactly what each event carries before you write a hook for it.

`scripts/event-logger.py` is a copy of the
[event-logger](https://github.com/karanb192/claude-code-hooks/blob/main/utils/event-logger.py)
utility from karanb192/claude-code-hooks, taken at
[`63e0354`](https://github.com/karanb192/claude-code-hooks/commit/63e0354bdf6ec56dd508d8ceef33b416ab6d8b14).
Changes from upstream:

- Packaged as a plugin: `hooks/hooks.json` registers the script for every
  event, where upstream has you wire it into `settings.json` by hand.

Upstream is MIT-licensed, © 2026 Karan Bansal.

## Install

```text
/plugin install hook-logger@sadv1r-agent-tools
```

It logs from the next session on. It writes on every event, tool calls
included, so disable it when you're done:

```text
/plugin disable hook-logger@sadv1r-agent-tools
```

## Logs

One file per day, `~/.claude/hooks-logs/YYYY-MM-DD.jsonl`, one line per event:

```json
{"ts": "2026-10-14T12:00:00.000000", "hook_event_name": "PreToolUse", "cwd": "/path/to/project", "data": {...}}
```

`data` is the payload as Claude Code sent it. Strings longer than 2000
characters and lists longer than 50 items are cut short.

```bash
tail -f ~/.claude/hooks-logs/$(date +%Y-%m-%d).jsonl | jq
cat ~/.claude/hooks-logs/*.jsonl | jq 'select(.hook_event_name=="PreToolUse")'
```

## Events

`hooks/hooks.json` registers the script for every hook event Claude Code
supports, except `WorktreeCreate` and `WorktreeRemove`: a hook on those
replaces Claude Code's own git worktree handling, so logging them would break
worktrees. To log a new event, add it to `hooks/hooks.json` and bump `version`
in `.claude-plugin/plugin.json`.

The script never prints to stdout and always exits 0, so it doesn't change
what any event does.

## Qwen Code

Not tested. Qwen Code has fewer hook events, so expect the ones it lacks to do
nothing there.
