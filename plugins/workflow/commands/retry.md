---
description: Resume whatever was in progress before an interruption (manual stop, network loss, error, crash)
---

The previous turn was interrupted before it finished (manual stop, network loss, error, crash). Pick up exactly where you left off.

1. Look at the conversation history and work out what you were doing when stopped: the task, the last step that completed, and the step that was cut off.
2. If a tool call was cut off, do not assume it succeeded or failed. Check the real state first, then redo the step only if it is still needed. Never repeat a step with side effects (commits, pushes, deletes, migrations, deploys, sent messages) without confirming it did not already happen.
3. If you were waiting on a suggestion to me or a decision from me, ask it again in full, with the same options, and wait for my answer.
4. If you had a plan or task list, continue from the first unfinished item. Do not restart the task from the beginning or redo work that is already done.
5. Before continuing, tell me in one line what you are resuming. Then carry on.

If you cannot tell what was in progress, say so and ask me what to resume rather than guessing.
