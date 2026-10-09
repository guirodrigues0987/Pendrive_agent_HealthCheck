"""
tools.py - System scan tools used by the agent.
Cross-platform: Windows and Linux.

Each function returns a list of dicts (JSON-friendly), designed to be easy
for a small LLM (7B-13B) to parse, since small models make fewer mistakes when
the input/output format is simple and consistent.
"""

import json
import os
import platform
import subprocess

import psutil

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

_WHITELIST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whitelist.json")


def load_whitelist():
    """Load whitelist.json. Returns empty sets if the file does not exist."""
    try:
        with open(_WHITELIST_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return (
            {p.lower() for p in data.get("processes", [])},
            {s.lower() for s in data.get("startup_items", [])},
        )
    except (FileNotFoundError, json.JSONDecodeError):
        return set(), set()


WHITELIST_PROCESSES, WHITELIST_STARTUP = load_whitelist()


# ---------------------------------------------------------------------------
# 1. Running processes
# ---------------------------------------------------------------------------
def list_processes(limit=30):
    """List running processes with CPU/memory usage. Cross-platform via psutil."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "username", "exe", "cpu_percent", "memory_percent"]):
        try:
            info = p.info
            name = info["name"] or ""
            procs.append(
                {
                    "pid": info["pid"],
                    "name": name,
                    "user": info.get("username"),
                    "path": info.get("exe"),
                    "cpu_percent": round(info.get("cpu_percent") or 0, 1),
                    "memory_percent": round(info.get("memory_percent") or 0, 1),
                    "whitelisted": name.lower() in WHITELIST_PROCESSES,
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    procs.sort(key=lambda x: x["memory_percent"], reverse=True)
    return procs[:limit]


# ---------------------------------------------------------------------------
# 2. Active network connections
# ---------------------------------------------------------------------------
def list_network_connections():
    """List active network connections (TCP/UDP) with the associated process."""
    conns = []
    try:
        for c in psutil.net_connections(kind="inet"):
            proc_name = None
            if c.pid:
                try:
                    proc_name = psutil.Process(c.pid).name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    proc_name = None
            conns.append(
                {
                    "pid": c.pid,
                    "process": proc_name,
                    "local_addr": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else None,
                    "remote_addr": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else None,
                    "status": c.status,
                }
            )
    except (psutil.AccessDenied, PermissionError):
        conns.append({"error": "Permission denied - run as administrator/root to see all connections"})
    return conns


# ---------------------------------------------------------------------------
# 3. Startup items - OS specific
# ---------------------------------------------------------------------------
def list_startup_items():
    """List programs/services configured to start with the system, flagging known ones."""
    if IS_WINDOWS:
        items = _list_startup_windows()
    elif IS_LINUX:
        items = _list_startup_linux()
    else:
        return [{"error": f"Unsupported OS: {platform.system()}"}]

    for item in items:
        if "error" in item:
            continue
        name = (item.get("name") or "").lower()
        item["whitelisted"] = any(w in name for w in WHITELIST_STARTUP)
    return items


def _list_startup_windows():
    items = []
    try:
        import winreg

        keys_to_check = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        ]
        for hive, path in keys_to_check:
            try:
                key = winreg.OpenKey(hive, path)
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        items.append({"name": name, "command": value, "source": path})
                        i += 1
                    except OSError:
                        break
            except FileNotFoundError:
                continue
    except ImportError:
        items.append({"error": "winreg unavailable (run on Windows)"})
    return items


def _list_startup_linux():
    items = []
    # Enabled systemd user/system services
    try:
        out = subprocess.run(
            ["systemctl", "list-unit-files", "--type=service", "--state=enabled"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in out.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[0].endswith(".service"):
                items.append({"name": parts[0], "type": "systemd", "state": parts[1]})
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # User's crontab
    try:
        out = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
        for line in out.stdout.splitlines():
            if line.strip() and not line.strip().startswith("#"):
                items.append({"name": "cron job", "command": line.strip(), "type": "cron"})
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # App autostart entries (.desktop)
    autostart_dir = os.path.expanduser("~/.config/autostart")
    if os.path.isdir(autostart_dir):
        for f in os.listdir(autostart_dir):
            if f.endswith(".desktop"):
                items.append({"name": f, "type": "autostart-desktop", "path": os.path.join(autostart_dir, f)})

    return items


# ---------------------------------------------------------------------------
# 4. Registry of all available tools (function-calling format)
# ---------------------------------------------------------------------------
TOOL_REGISTRY = {
    "list_processes": list_processes,
    "list_network_connections": list_network_connections,
    "list_startup_items": list_startup_items,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_processes",
            "description": "List the running processes on the system, with CPU and memory usage.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_network_connections",
            "description": "List active network connections (TCP/UDP) and the process associated with each.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_startup_items",
            "description": (
                "List programs, services and tasks configured to start automatically with the system."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


if __name__ == "__main__":
    # Quick standalone test
    print(
        json.dumps(
            {
                "processes_sample": list_processes(limit=5),
                "startup_items": list_startup_items()[:5],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
