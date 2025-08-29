#!/usr/bin/env bash
set -euo pipefail

AFTER="$(readlink -f ./closeVM.sh)"   # the script you want to run after closing
chmod +x "$AFTER" 2>/dev/null || true

# Arm trap only after tmux successfully starts so we don't run AFTER on early failures.
ran_tmux=0
trap '[[ $ran_tmux -eq 1 ]] && "$AFTER"' EXIT HUP INT TERM

./startVM.sh

SESSION="seedscan"
PY="${PYTHON_BIN:-python3}"
B1="$(readlink -f ./parallelscan_BATCH1.py)"
B2="$(readlink -f ./parallelscan_BATCH2.py)"

CMD_B1="bash -lc '$PY \"$B1\"; echo; echo \"[Batch 1 exited] press Ctrl-D to close\"; exec bash'"
CMD_B2="bash -lc '$PY \"$B2\"; echo; echo \"[Batch 2 exited] press Ctrl-D to close\"; exec bash'"

if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux new-session -d -s "$SESSION" -n "SeedScan" "$CMD_B1"
  tmux split-window -h -t "$SESSION:0" "$CMD_B2"
  tmux select-pane -t "$SESSION:0.0" \; select-pane -T "Batch 1 (101–104)"
  tmux select-pane -t "$SESSION:0.1" \; select-pane -T "Batch 2 (105–108)"
  tmux set-option -t "$SESSION" mouse on
fi

ran_tmux=1

# Attach first, THEN set destroy-unattached so closing the terminal kills the session.
tmux attach -t "$SESSION" \; set-option -t "$SESSION" destroy-unattached on
