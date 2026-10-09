"""
history.py - Scan history and comparison between runs.

Each scan is saved as a JSON snapshot in scans/, with a timestamp in the name.
On every new run we compare against the most recent previous snapshot to
highlight ONLY what changed (new process, new startup item, new connection).
This greatly reduces noise and helps the LLM (and you) focus on what actually
matters instead of re-reading the same huge list every time.
"""

import json
import os
from datetime import datetime

SCANS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scans")


def _ensure_dir():
    os.makedirs(SCANS_DIR, exist_ok=True)


def list_snapshots():
    """Return the paths of saved snapshots, in chronological order."""
    _ensure_dir()
    files = [f for f in os.listdir(SCANS_DIR) if f.startswith("scan_") and f.endswith(".json")]
    files.sort()
    return [os.path.join(SCANS_DIR, f) for f in files]


def load_latest_snapshot():
    """Load the most recent saved snapshot, or None if there is none."""
    snapshots = list_snapshots()
    if not snapshots:
        return None
    with open(snapshots[-1], encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(processes, connections, startup_items):
    """Save a new timestamped snapshot and return the file path."""
    _ensure_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCANS_DIR, f"scan_{timestamp}.json")
    data = {
        "timestamp": timestamp,
        "processes": processes,
        "connections": connections,
        "startup_items": startup_items,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def _names(items, key="name"):
    """Extract a set of names/identifiers from a list of dicts, ignoring error entries."""
    result = set()
    for item in items:
        if not isinstance(item, dict) or "error" in item:
            continue
        val = item.get(key)
        if val:
            result.add(val)
    return result


def diff_snapshots(previous, current_processes, current_connections, current_startup):
    """
    Compare the previous snapshot with the current data and return a dict with
    what is NEW in each category (present now but not before).
    If there is no previous snapshot (first scan), return None.
    """
    if previous is None:
        return None

    prev_proc_names = _names(previous.get("processes", []), "name")
    prev_conn_remotes = _names(previous.get("connections", []), "remote_addr")
    prev_startup_names = _names(previous.get("startup_items", []), "name")

    curr_proc_names = _names(current_processes, "name")
    curr_conn_remotes = _names(current_connections, "remote_addr")
    curr_startup_names = _names(current_startup, "name")

    return {
        "previous_timestamp": previous.get("timestamp"),
        "new_processes": sorted(curr_proc_names - prev_proc_names),
        "new_remote_connections": sorted(curr_conn_remotes - prev_conn_remotes),
        "new_startup_items": sorted(curr_startup_names - prev_startup_names),
    }
