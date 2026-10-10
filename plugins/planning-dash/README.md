# planning-dash

A live dashboard for a `/planning:exec` run, shown in an [agterm](https://agterm.com) HTML
overlay: the tasks and their checklists, the review phases, every subagent with its tool calls
and context size, a timeline with a forecast, the decisions the subagents made on their own, and
the progress log. It also keeps the run's progress in the exec session's title bar.

It reads what the [`planning`](../planning) plugin's `exec` skill writes: the plan's checkboxes,
the run's progress file and the session's transcripts. macOS only: it drives agterm through
`agtermctl` and finds the exec session through `ps -E`. Nothing runs until you bind the key
below; outside agterm the plugin's hook does nothing.

## Install

```text
/plugin install planning-dash@sadv1r-agent-tools
```

Then bind the toggle in `~/.config/agterm/keymap.conf`. It opens the dashboard of the run the
session's own Claude Code started, or else the newest run of the session's project, over the
session, and closes it on the next press:

```
command "Exec dashboard" cmd+shift+e --error-hud /opt/homebrew/bin/python3 "$HOME/.claude/plugins/marketplaces/sadv1r-agent-tools/plugins/planning-dash/scripts/exec-dash.py" --toggle --project "$AGT_SESSION_PWD" --target "$AGT_SESSION_ID" --socket "$AGT_SOCKET"
```

The path is the marketplace checkout, which `/plugin marketplace update` keeps current. Keymap
commands run with the app's own PATH, so give `python3` as a full path; any Python 3.9 or later
does, `/usr/bin/python3` included.

When a run initializes its progress file, the plugin's `PostToolUse` hook shows a HUD on the
session with the key you bound. It reads the chord from the keymap line above, so there is
nothing else to configure; without a binding it stays silent.

## Usage

```
exec-dash.py --toggle --project DIR      open the session's own run, else the newest run of DIR's project; close it when open
exec-dash.py PLAN --open                 open a given plan's dashboard
exec-dash.py PLAN --stop                 stop that plan's watcher
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `PLAN` | the `--target` session's own run, else the newest run of `--project` | plan file to show |
| `--project DIR` | the plan's project, else cwd | any directory inside the project (the one holding `docs/plans`) |
| `--open` | | open the dashboard in an overlay |
| `--toggle` | | open the dashboard, or close it when it is already open |
| `--stop` | | stop the plan's watcher |
| `--target ID` | `$AGTERM_SESSION_ID` | session to show the overlay on; the run its Claude Code started is the default `PLAN` |
| `--socket PATH` | `$AGTERM_SOCKET` | agterm control socket |
| `--no-title` | | leave the exec session's title-bar context line alone |
| `--interval SEC` | 3 | seconds between refreshes |
| `--stall SEC` | 600 | show the "Quiet for" warning after this long without any write |
| `--context-limit N` | 200000 | the context window the orchestrator's context is measured against; the header turns amber at 80% |

## How it works

`exec-dash.py` starts a background watcher that every few seconds reads

- the plan's `### Task N:` sections and their `- [ ]` checkboxes,
- the run's progress file, `/tmp/progress-<plan-stem>.txt`, whose `Plan:` header names the plan,
- the subagent transcripts under `~/.claude/projects/<project>/<session>/subagents/`,
- the orchestrator's own transcript: the `--- Review phase N ---` lines it prints before a phase,
  the launch result of each `Agent` call, the hand-back or task notification that tells it a
  subagent finished, and its own context size at its latest request,

and writes `data.js` next to a copy of `exec-dash.html` in `~/.cache/exec-dash/<plan-stem>/`.
The page polls `data.js`, so a watcher restart or a page reload never loses anything. The watcher
stops on its own two minutes after the run completes, or after three hours without any activity;
opening the dashboard again restarts it.

Without a `PLAN`, the run shown is the one the `--target` session's own Claude Code started: the
script finds the live process in that session (`~/.claude/sessions/<pid>.json` and the process
environment, through `ps -E`) and takes the progress file its transcript initialized last. Two
exec sessions of one project each get their own dashboard, watcher and title line. A session
without such a process, a plain shell say, gets the project's newest run. The toggle closes
whichever exec dashboard is open on the session.

It also keeps the run in the exec session's title bar, as the session's context line:
`<plan heading>: 4/11` while the tasks run, `11/11 · review 1 ×2` during a review phase (the
count is its iteration), `11/11 · done` at completion. The line is only ever written over an empty
title bar or over a line of its own, so a context you set yourself stays, and the watcher clears it
when it stops. `--no-title` turns this off.

A run moved into a worktree under `.claude/worktrees/` ticks the plan copy there; the copy on the
run's branch is the one read, and the project's copy (or `docs/plans/completed/`) is the fallback
once the worktree is gone.

## What the dashboard shows

**Status pill** (top right), first match wins:

| Pill | Meaning |
| --- | --- |
| Completed | the progress file has its `completed` entry |
| Watcher stopped | `data.js` is older than six refresh intervals; reopen the dashboard |
| API error | the orchestrator or a running subagent printed an `API Error` and nothing followed |
| Needs your input | the exec session is asking a question |
| Quiet for Xm | nothing was written for longer than `--stall` |
| Running | a subagent is working |
| Orchestrating | no subagent, but the exec session is active |
| Idle | nothing is happening |

**Banners** appear under the title for the warning states:

- *No fresh data* — the watcher is gone; close and reopen the dashboard to restart it.
- *API error* — quotes the error and when it was printed. A `403` with `Please run /login` means
  the session needs a login before the run goes on; the orchestrator does not retry by itself.
- *Waiting for you* — the orchestrator is asking a question in its session.
- *Quiet for Xm* — nothing was written to any transcript, the progress file or the plan since the
  time shown, with the last tool call. A long test run looks like this too; a dead run does as well,
  so check the session when the last tool call does not explain the silence.

**Header line**: the plan's path and branch, when the run started, and the orchestrator's model
and context size at its latest request (`orchestrator opus 5.5 · 176k`). The context is the
number auto-compaction watches: it turns amber at 80% of `--context-limit`, when a compaction
before the review fan-out is likely. Hover it for the exact count and the share of the limit.

**Open exec session** (top right) switches to the orchestrator's session, for a dashboard opened
over another session of the same project.

Models are shown short (`claude-opus-5-5` as `opus 5.5`): with the orchestrator in the header,
with every running subagent in the Now card, on every attempt in the task and phase details, and
summed up in the footer (`subagents on opus 5.5`, or `opus 5.5 ×5 · sonnet 4.5 ×2` when they
differ).

**Tiles**: tasks done, elapsed time, the average task time, the forecast for the remaining tasks,
and tool calls across subagents.

**Now**: the running task with its subagent's last tool call, context size and any API error;
during reviews, every running subagent; between steps, the orchestrator with its context size.

**Steps**: the run in order, one row per plan task followed by the four review phases, finalize and
stats. Click a task for the checklist, the files it touches, each attempt with its duration, tool
calls and context, and its progress notes, with `[decision]` and `[deviation]` entries tagged. The
running task opens by itself and closes again when the next one starts. Click a phase for its
subagents; its progress column shows the iterations and agents. A phase is "skipped" when the
progress file says it was not run.

**Timeline**: a Gantt of tasks and phases, with a forecast of the remaining tasks at the average
task time.

**Decisions and deviations**: every judgment call the subagents logged, with the task or fixer
that made it. The card only appears once there is one.

**Progress log**: the progress file newest first; click an entry for its details (up to 400
lines, with a note when the file holds more).

## Files

```
~/.cache/exec-dash/<plan-stem>/
  index.html    copy of exec-dash.html
  data.js       the latest snapshot, rewritten every --interval seconds
  watcher.pid   the watcher's pid while it runs
  watcher.log   its stderr (empty unless something went wrong)
```
