---
description: "Stop a running auto-run research loop"
---

# /cancel-loop

Stops the currently active research loop.

## Steps

1. Check if `_autonomous/loop.state.md` exists
2. If yes:
   - Delete `_autonomous/loop.state.md`
   - Run `tmux kill-session -t autorun 2>/dev/null` to clean up any tmux session
   - Confirm: "Research loop cancelled. State file removed and tmux session killed."
3. If no: "No active research loop found."
