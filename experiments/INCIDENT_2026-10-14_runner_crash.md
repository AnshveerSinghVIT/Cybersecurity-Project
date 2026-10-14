# Incident: queue runner crashed during exp003 (2026-10-14 20:00:41)

## What happened
- `run_queue.py` (PID 24104, launched 19:46:11 via WMI) terminated at 20:00:41 while monitoring
  `exp003_cross_family`. Its `finally` block ran: `queue_status.json` shows `finished: true`,
  `stop_reason: null`, `not_run: [exp005_dedup_sensitivity, exp004_leakage_vs_drift]`, and the exp003
  step still marked `running` (status never updated).
- Integrity checks written by the `finally` block: datasets, sources and exp001 artifacts unchanged.
- The exp003 process (PID 32248) was NOT terminated: it continued as an orphan, writing to its own
  `exp003_cross_family/run.log` and per-seed JSONs. It is no longer covered by the memory guard,
  the timeout, or the runner's exit-code / required-output check.
- exp005 and exp004 never started. No experiment run failed.

## Most likely cause (inferred, not proven)
The runner rewrote `queue_status.json` every 5 s with `os.replace(tmp, STATUS)`. On Windows this
raises PermissionError if another process holds the destination open. Two readers held it open
periodically: the assistant's completion waiter (every 60 s) and a manual status check at about
20:00:30. The monitoring loop had no exception handling, and the runner's own stdout/stderr were not
captured (WMI launch, no redirection), so **no traceback exists**. The cause is inferred from timing
and the Windows semantics of os.replace; it could not be confirmed.

## Defects in the runner (to fix before any relaunch)
1. `save()` must tolerate a transiently locked destination (retry, and never let a status-write error
   kill the queue).
2. The monitoring loop must catch and record unexpected exceptions with traceback, and must not leave
   a child running unmonitored.
3. The runner's own stdout/stderr must go to a log file.
4. Status readers should not open the live file (read a copy, or the runner writes a separate
   read-only snapshot).

## Evidence preserved
- `queue_status.json`, `queue.log` (unchanged since the crash)
- `exp003_cross_family/run.log`, `run_seed42.json`, `run_seed1.json`, `data_prep.json`
- `gate_loader_equivalence/` (completed, passed)

## Update (follow-up)
- Mechanism reproduced: with a reader holding the status file open, the old `os.replace` write
  fails on Windows; the fixed `save()` retries and succeeds once the reader closes (tested).
- The four runner defects above were fixed in `run_queue.py` before the second queue run.
- First-run status files archived as `queue_status_run1.json` and `queue_run1.log`.
