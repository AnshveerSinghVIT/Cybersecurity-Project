"""
Unattended, sequential experiment queue.

Guarantees
  - strictly one experiment process at a time
  - keeps Windows awake while running (SetThreadExecutionState; released on exit). Lid-close
    standby cannot be blocked by software.
  - each step's stdout/stderr -> experiments/<id>/run.log (an existing log is kept, renamed)
  - experiments write each run's JSON as it finishes, so completed runs survive later failures
  - memory guard: if system available RAM stays < GUARD_AVAIL_GB for GUARD_SECONDS, the step is
    killed and recorded as failed (prevents a paging death-spiral); peak working set is recorded
  - per-step timeout; no retries; configuration is never changed by the runner
  - integrity: sha256 of every source file, the frozen exp001 artifacts and every dataset file is
    taken before the queue and re-checked after each step; any change stops the queue
  - status: experiments/queue_status.json (rewritten after every event) + experiments/queue.log
  - a step counts as COMPLETED only if exit code 0 AND its required output files exist

Fixes after the 2026-10-14 20:00 crash (experiments/INCIDENT_2026-10-14_runner_crash.md)
  - status writes retry when the file is briefly locked by a reader and can never kill the queue
  - unexpected errors in the monitoring loop are recorded with traceback; the child is never orphaned
  - unexpected errors in the queue loop are recorded with traceback as the stop reason
  - completion is signalled by an empty marker file experiments/QUEUE_DONE (watchers test existence
    only and never open the live status file)
  - precondition: ids_common.py must be byte-identical to the revision that passed the loader gate
  - the runner's own stdout/stderr is redirected to experiments/runner_stdout.log by the launcher

Continue/stop policy after a failed step
  - gate failure (loader not equivalent to exp001)          -> stop (all later steps depend on it)
  - memory guard / low disk / integrity violation          -> stop (environment not safe)
  - ordinary experiment failure (exception, timeout)       -> record and continue: the remaining
    experiments are independent (each reads only raw data + frozen exp001)
"""
import ctypes
import datetime as dt
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback

import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
EXPD = os.path.join(HERE, "experiments")
STATUS = os.path.join(EXPD, "queue_status.json")
QLOG = os.path.join(EXPD, "queue.log")
DONE = os.path.join(EXPD, "QUEUE_DONE")
GATE_SNAPSHOT = os.path.join(EXPD, "gate_loader_equivalence", "code", "ids_common.py")
PY = sys.executable

GUARD_AVAIL_GB = 0.4
GUARD_SECONDS = 120
MIN_FREE_DISK_GB = 5
POLL = 5

QUEUE = [
    {"id": "exp006_shift_diagnosis", "cmd": ["exp006_shift_diagnosis.py"], "timeout_min": 60,
     "required": ["MANIFEST.json", "summary.md", "summary.json"]},
    {"id": "exp007_shift_mitigation", "cmd": ["exp007_shift_mitigation.py"], "timeout_min": 180,
     "required": ["MANIFEST.json", "summary.md"]},
    {"id": "exp004_leakage_vs_drift", "cmd": ["exp004_leakage_vs_drift.py", "--seeds", "42", "1"],
     "timeout_min": 150, "required": ["MANIFEST.json", "summary.md", "data_prep.json"]},
    {"id": "exp005_dedup_sensitivity", "cmd": ["exp005_dedup_sensitivity.py", "--seeds", "42"],
     "timeout_min": 120, "required": ["MANIFEST.json", "summary.md", "data_prep.json"]},
]

SOURCES = ["ids_common.py", "verify_loader.py", "run_queue.py", "exp002_seeds.py",
           "exp003_cross_family.py", "exp004_leakage_vs_drift.py", "exp005_dedup_sensitivity.py",
           "exp006_shift_diagnosis.py", "exp007_shift_mitigation.py",
           "multiclass_baseline.py"]


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def log(msg):
    line = f"[{now()}] {msg}"
    print(line, flush=True)
    with open(QLOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint_sources():
    return {s: sha256(os.path.join(HERE, s)) for s in SOURCES if os.path.exists(os.path.join(HERE, s))}


def fingerprint_exp001():
    d = os.path.join(EXPD, "exp001_baseline")
    return {f: sha256(os.path.join(d, f)) for f in sorted(os.listdir(d))}


def fingerprint_datasets():
    out = {}
    for pat in ("cicids2017/*.csv", "cicids2018/*.csv", "cicids2017_labelled/*.zip"):
        for p in sorted(glob.glob(os.path.join(HERE, pat))):
            out[os.path.relpath(p, HERE)] = sha256(p)
    return out


def keep_awake(on):
    try:
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))
        return True
    except Exception:
        return False


def save(state):
    """Write the status file atomically; tolerate readers briefly locking it (Windows). Never raises."""
    tmp = STATUS + ".tmp"
    for attempt in range(40):
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            os.replace(tmp, STATUS)
            return True
        except OSError:
            time.sleep(0.25)
    try:
        with open(QLOG, "a", encoding="utf-8") as f:
            f.write(f"[{now()}] WARNING: status file write failed 40 times; continuing" + chr(10))
    except OSError:
        pass
    return False


def tail(path, n=50):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.readlines()[-n:]
    except OSError:
        return []


def run_step(step, state):
    sid = step["id"]
    out_dir = os.path.join(EXPD, sid)
    os.makedirs(out_dir, exist_ok=True)
    run_log = os.path.join(out_dir, "run.log")
    if os.path.exists(run_log):
        os.replace(run_log, run_log + f".prev-{int(time.time())}")
    rec = {"id": sid, "cmd": [os.path.basename(PY)] + step["cmd"], "status": "running", "start": now()}
    state["steps"].append(rec)
    save(state)
    log(f"START {sid}: {' '.join(step['cmd'])}")

    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    t0 = time.time()
    peak_ws, min_avail, low_since, killed_reason = 0, 1e9, None, None
    with open(run_log, "w", encoding="utf-8") as lf:
        proc = subprocess.Popen([PY, "-u"] + step["cmd"], cwd=HERE, stdout=lf, stderr=subprocess.STDOUT, env=env)
        ps = psutil.Process(proc.pid)
        while proc.poll() is None:
          try:
            try:
                mi = ps.memory_info()
                peak_ws = max(peak_ws, getattr(mi, "peak_wset", mi.rss))
            except psutil.Error:
                pass
            avail = psutil.virtual_memory().available / 1e9
            min_avail = min(min_avail, avail)
            if avail < GUARD_AVAIL_GB:
                low_since = low_since or time.time()
                if time.time() - low_since > GUARD_SECONDS:
                    killed_reason = f"memory_guard: available RAM < {GUARD_AVAIL_GB} GB for > {GUARD_SECONDS}s"
            else:
                low_since = None
            if time.time() - t0 > step["timeout_min"] * 60:
                killed_reason = f"timeout: exceeded {step['timeout_min']} min"
            if killed_reason:
                log(f"KILL {sid}: {killed_reason}")
                proc.kill()
                proc.wait()
                break
            rec.update({"elapsed_sec": round(time.time() - t0), "peak_working_set_gb": round(peak_ws / 1e9, 2),
                        "min_system_available_gb": round(min_avail, 2)})
            save(state)
          except Exception:
            # never let a monitoring error orphan the child: record it and keep waiting
            rec.setdefault("monitor_errors", []).append(traceback.format_exc())
          time.sleep(POLL)
    rc = proc.returncode
    missing = [f for f in step["required"] if not os.path.exists(os.path.join(out_dir, f))]
    rec.update({"end": now(), "elapsed_sec": round(time.time() - t0), "exit_code": rc,
                "peak_working_set_gb": round(peak_ws / 1e9, 2), "min_system_available_gb": round(min_avail, 2),
                "missing_outputs": missing})
    runs_dir = os.path.join(out_dir, "runs")
    rec["run_files_saved"] = sorted(os.listdir(runs_dir)) if os.path.isdir(runs_dir) else \
        sorted(f for f in os.listdir(out_dir) if f.startswith("run_seed"))
    if rc == 0 and not missing and not killed_reason:
        rec["status"] = "completed"
        log(f"DONE {sid} in {rec['elapsed_sec']}s, peak {rec['peak_working_set_gb']} GB")
    else:
        rec["status"] = "failed"
        rec["failure_reason"] = killed_reason or (f"exit code {rc}" if rc != 0 else f"missing outputs {missing}")
        rec["log_tail"] = tail(run_log)
        log(f"FAILED {sid}: {rec['failure_reason']} (log preserved: {os.path.relpath(run_log, HERE)})")
    save(state)
    return rec, killed_reason


def main():
    os.makedirs(EXPD, exist_ok=True)
    if os.path.exists(DONE):
        os.remove(DONE)
    state = {"queue_started": now(), "finished": False, "python": PY, "steps": [],
             "keep_awake": keep_awake(True)}
    save(state)
    log(f"queue start (pid {os.getpid()}), keep_awake={state['keep_awake']}")
    log("fingerprinting sources, exp001 artifacts and datasets ...")
    src0, e0010, data0 = fingerprint_sources(), fingerprint_exp001(), fingerprint_datasets()
    state["fingerprints_before"] = {"sources": src0, "exp001": e0010, "datasets": data0}
    save(state)
    stop_reason = None
    try:
        if sha256(os.path.join(HERE, "ids_common.py")) != sha256(GATE_SNAPSHOT):
            stop_reason = "ids_common.py differs from the revision that passed the loader gate"
            raise SystemExit
        log("precondition OK: ids_common.py identical to the gate-verified revision")
        for step in QUEUE:
            free = shutil.disk_usage(HERE).free / 1e9
            if free < MIN_FREE_DISK_GB:
                stop_reason = f"low disk: {free:.1f} GB free"
                break
            rec, killed = run_step(step, state)
            src1, e0011 = fingerprint_sources(), fingerprint_exp001()
            if src1 != src0 or e0011 != e0010:
                changed = [k for k in set(src0) | set(src1) if src0.get(k) != src1.get(k)] + \
                          [f"exp001/{k}" for k in set(e0010) | set(e0011) if e0010.get(k) != e0011.get(k)]
                stop_reason = f"integrity violation after {step['id']}: changed {changed}"
                break
            if rec["status"] == "failed":
                if step.get("gate"):
                    stop_reason = f"gate {step['id']} failed - later steps depend on it"
                    break
                if killed and killed.startswith("memory_guard"):
                    stop_reason = f"memory guard tripped in {step['id']} - environment unsafe"
                    break
                log(f"continuing after failure of {step['id']} (remaining experiments are independent)")
    except SystemExit:
        pass
    except Exception:
        stop_reason = "runner error: " + traceback.format_exc()
        log(stop_reason)
    finally:
        data1 = fingerprint_datasets()
        state["fingerprints_after"] = {"sources": fingerprint_sources(), "exp001": fingerprint_exp001(),
                                       "datasets": data1}
        state["datasets_unchanged"] = data1 == data0
        state["sources_unchanged"] = state["fingerprints_after"]["sources"] == src0
        state["exp001_unchanged"] = state["fingerprints_after"]["exp001"] == e0010
        done_ids = {s["id"] for s in state["steps"]}
        state["not_run"] = [s["id"] for s in QUEUE if s["id"] not in done_ids]
        state["stop_reason"] = stop_reason
        state["queue_finished"] = now()
        state["finished"] = True
        save(state)
        keep_awake(False)
        open(DONE, "w").close()
        log(f"queue end. stop_reason={stop_reason} not_run={state['not_run']} "
            f"datasets_unchanged={state['datasets_unchanged']} sources_unchanged={state['sources_unchanged']} "
            f"exp001_unchanged={state['exp001_unchanged']}")


if __name__ == "__main__":
    main()
