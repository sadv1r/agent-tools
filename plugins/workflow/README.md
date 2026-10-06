# workflow

Slash commands for steering a session.

| Command | What it does |
|---|---|
| `/retry` | Resumes whatever was in progress before an interruption (manual stop, network loss, error, crash). It checks the real state of any tool call that was cut off, won't repeat side effects such as commits or pushes without confirming they didn't already happen, and re-asks any pending question |

In Claude Code the command is also available as `/workflow:retry`.
