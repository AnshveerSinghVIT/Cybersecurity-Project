"""
Read-only progress check for the experiment queue. Changes nothing, starts nothing.

  python check_progress.py            # one snapshot
  python check_progress.py --watch    # refresh every 30 s (Ctrl+C to stop)
"""
import datetime as dt
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXPD = os.path.join(HERE, "experiments")

# (experiment id, folder with per-run JSONs, glob, expected number of runs, fallback seconds/run, load overhead s)
PLAN = [
    ("exp006_shift_diagnosis", None, None, 1, 290, 0),
    ("exp007_shift_mitigation", "exp007_shift_mitigation/runs", "*.json", 30, 120, 240),
    ("exp004_leakage_vs_drift", "exp004_leakage_vs_drift/runs", "*.json", 14, 170, 300),
    ("exp005_dedup_sensitivity", "exp005_dedup_sensitivity/runs", "*.json", 9, 150, 240),
]


def j(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def mins(s):
    return f"{int(s // 3600)}h {int(s % 3600 // 60):02d}m" if s >= 3600 else f"{int(s // 60)}m"


def snapshot():
    now = dt.datetime.now()
    out = [f"=== Queue progress, {now:%H:%M:%S} ==="]
    qs = j(os.path.join(EXPD, "queue_status.json")) or {}
    done_marker = os.path.exists(os.path.join(EXPD, "QUEUE_DONE"))
    steps = {s["id"]: s for s in qs.get("steps", [])}
    eta, started_any = 0.0, False
    rows = []
    for eid, rdir, pat, expected, fallback, overhead in PLAN:
        st = steps.get(eid, {})
        status = st.get("status", "not started")
        if rdir:
            files = glob.glob(os.path.join(EXPD, rdir, pat))
            done = len(files)
            times = [r.get("runtime_sec") for r in (j(f) for f in files) if r and r.get("runtime_sec")]
        else:
            done = 1 if status == "completed" else 0
            times = []
        per = (sum(times) / len(times)) if times else fallback
        if status == "completed":
            remaining_s = 0
        elif status == "running":
            remaining_s = max(expected - done, 0) * per
            started_any = True
        else:
            remaining_s = expected * per + overhead
        eta += remaining_s
        rows.append((eid, status, f"{done}/{expected}", mins(remaining_s) if remaining_s else "-",
                     st.get("peak_working_set_gb", "")))
    w = max(len(r[0]) for r in rows)
    out.append(f"{'experiment'.ljust(w)}  {'status':<12} {'runs':<7} {'est. left':<9} peak GB")
    for r in rows:
        out.append(f"{r[0].ljust(w)}  {r[1]:<12} {r[2]:<7} {r[3]:<9} {r[4]}")
    if done_marker or qs.get("finished"):
        failed = [s["id"] for s in qs.get("steps", []) if s.get("status") == "failed"]
        out.append("")
        out.append("QUEUE FINISHED at " + str(qs.get("queue_finished")) +
                   (f"  | FAILED: {failed}" if failed else "  | no failed steps") +
                   (f"  | stop reason: {qs.get('stop_reason')}" if qs.get("stop_reason") else ""))
    else:
        finish = now + dt.timedelta(seconds=eta)
        out.append("")
        out.append(f"Estimated time left: {mins(eta)}  (finishes about {finish:%H:%M})")
        out.append("(estimate = remaining runs x average time of runs already finished; rough)")
    log = os.path.join(EXPD, "queue.log")
    if os.path.exists(log):
        with open(log, encoding="utf-8", errors="replace") as f:
            last = f.readlines()[-3:]
        out.append("")
        out.append("Last log lines:")
        out += ["  " + x.rstrip() for x in last]
    return "\n".join(out)


if __name__ == "__main__":
    if "--watch" in sys.argv:
        try:
            while True:
                os.system("cls" if os.name == "nt" else "clear")
                print(snapshot())
                time.sleep(30)
        except KeyboardInterrupt:
            pass
    else:
        print(snapshot())
