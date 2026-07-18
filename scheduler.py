# scheduler.py
"""In-container scheduler for the periodic scrape jobs.

Replaces the one-shot container CMD: runs forever and kicks off each job
when its interval has elapsed — sequentially, never in parallel (the
saflii.org rate limit and the shared collection tolerate no concurrency).
Lives entirely inside the container so it runs wherever the container
runs (NAS today, customer server later); no Synology task scheduler or
host cron involved.

Jobs (intervals in days, 0 disables a job):
  - saflii-scrape, then reconcile --apply   SAFLII_SCRAPE_INTERVAL_DAYS (default 7)
  - rules-collect (--apply)                 RULES_INTERVAL_DAYS (default 30)

ragflow_sync is deliberately not scheduled: RAGFlow currently runs on
Rafael's Mac and is not reachable from the NAS container — the sync
stays a manual step (see README).

Last-run timestamps live in a JSON state file on the data volume
(SCHEDULER_STATE_FILE, default <SAFLII_DATA_DIR>/logs/scheduler_state.json)
so container redeploys do not reset the clock. On the very first start
the state is initialised to "just ran": deploying the scheduler never
triggers a surprise days-long full scrape. For an immediate manual run:

    docker exec <container> /app/.venv/bin/python saflii_processor_yearly.py
    docker exec <container> /app/.venv/bin/python rules_collector.py --apply
"""

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta

from saflii_processor_yearly import DEFAULT_DATA_DIR, notify_ntfy

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
log = logging.getLogger("scheduler")

CHECK_INTERVAL_SECONDS = 15 * 60

DATA_DIR = os.environ.get("SAFLII_DATA_DIR", DEFAULT_DATA_DIR)
STATE_FILE = os.environ.get("SCHEDULER_STATE_FILE") or os.path.join(
    DATA_DIR, "logs", "scheduler_state.json"
)

JOBS = [
    {
        "name": "saflii-scrape",
        "interval_env": "SAFLII_SCRAPE_INTERVAL_DAYS",
        "default_days": 7,
        # Reconcile follows every successful re-scrape: title corrections
        # leave duplicates behind that must not reach the RAGFlow sync.
        "commands": [
            [sys.executable, "saflii_processor_yearly.py"],
            [sys.executable, "reconcile.py", DATA_DIR, "--apply"],
        ],
    },
    {
        "name": "rules-collect",
        "interval_env": "RULES_INTERVAL_DAYS",
        "default_days": 30,
        "commands": [[sys.executable, "rules_collector.py", "--apply"]],
    },
]


def job_interval(job):
    try:
        return timedelta(days=float(os.environ.get(job["interval_env"], job["default_days"])))
    except ValueError:
        log.error(
            f"Invalid {job['interval_env']}={os.environ[job['interval_env']]!r}, "
            f"using default {job['default_days']} days"
        )
        return timedelta(days=job["default_days"])


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return {name: datetime.fromisoformat(ts) for name, ts in json.load(f).items()}
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        log.warning(f"Could not read scheduler state {STATE_FILE}: {e} — starting fresh")
        return None


def save_state(state):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({name: ts.isoformat() for name, ts in state.items()}, f, indent=2)
    except OSError as e:
        log.warning(f"Could not write scheduler state {STATE_FILE}: {e}")


def run_job(job):
    """Run the job's command chain; abort the chain on the first failure."""
    for command in job["commands"]:
        pretty = " ".join(os.path.basename(part) for part in command)
        log.info(f"[{job['name']}] starting: {pretty}")
        result = subprocess.run(command, stdin=subprocess.DEVNULL)
        if result.returncode != 0:
            log.error(f"[{job['name']}] step failed (exit {result.returncode}): {pretty}")
            notify_ntfy(
                f"Scheduler: job {job['name']} failed at '{pretty}' "
                f"(exit {result.returncode})",
                priority="high",
            )
            return False
    log.info(f"[{job['name']}] finished")
    return True


def main():
    state = load_state()
    if state is None:
        # First start: mark everything as freshly run so a (re)deploy never
        # kicks off a surprise multi-day scrape. Manual runs via docker exec.
        state = {job["name"]: datetime.now() for job in JOBS}
        save_state(state)
        log.info(f"First start, initialised state at {STATE_FILE}")

    for job in JOBS:
        interval = job_interval(job)
        if not interval:
            log.info(f"[{job['name']}] disabled ({job['interval_env']}=0)")
        else:
            due = state.get(job["name"], datetime.min) + interval
            log.info(f"[{job['name']}] every {interval.days} day(s), next run due {due:%Y-%m-%d %H:%M}")

    while True:
        for job in JOBS:
            interval = job_interval(job)  # re-read: env fixed, but cheap
            if not interval:
                continue
            last_run = state.get(job["name"], datetime.min)
            if datetime.now() - last_run < interval:
                continue
            # Record the attempt regardless of outcome: a failed scrape
            # already alerts via ntfy, and retrying a multi-day crawl in a
            # 15-minute loop would hammer saflii.org's rate limit.
            run_job(job)
            state[job["name"]] = datetime.now()
            save_state(state)
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
