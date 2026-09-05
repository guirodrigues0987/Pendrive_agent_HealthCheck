"""
tools.py — Ferramentas de scan do sistema, usadas pelo agente.
Cross-platform: Windows e Linux.

Cada função retorna uma lista de dicts (JSON-friendly), pensado pra ser
fácil de parsear por um LLM pequeno (7B-13B) que erra menos quando o
formato de entrada/saída é simples e consistente.
"""

import platform
import subprocess
import json
import os
import psutil


IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

_WHITELIST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whitelist.json")


def load_whitelist():
    """Carrega whitelist.json. Retorna listas vazias se o arquivo não existir."""
    try:
        with open(_WHITELIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (
            {p.lower() for p in data.get("processes", [])},
            {s.lower() for s in data.get("startup_items", [])},
        )
    except (FileNotFoundError, json.JSONDecodeError):
        return set(), set()


WHITELIST_PROCESSES, WHITELIST_STARTUP = load_whitelist()


# ---------------------------------------------------------------------------
# 1. Processos em execução
# ---------------------------------------------------------------------------
def list_processes(limit=30):
    """Lista processos rodando com uso de CPU/memória. Cross-platform via psutil."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "username", "exe", "cpu_percent", "memory_percent"]):
        try:
            info = p.info
            name = info["name"] or ""
            procs.append({
                "pid": info["pid"],
                "name": name,
                "user": info.get("username"),
                "path": info.get("exe"),
                "cpu_percent": round(info.get("cpu_percent") or 0, 1),
                "memory_percent": round(info.get("memory_percent") or 0, 1),
                "whitelisted": name.lower() in WHITELIST_PROCESSES,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    procs.sort(key=lambda x: x["memory_percent"], reverse=True)
    return procs[:limit]


# ---------------------------------------------------------------------------
# 2. Conexões de rede ativas
# ---------------------------------------------------------------------------
def list_network_connections():
    """Lista conexões de rede ativas (TCP/UDP) com processo associado."""
    conns = []
    try:
        for c in psutil.net_connections(kind="inet"):
            proc_name = None
            if c.pid:
                try:
                    proc_name = psutil.Process(c.pid).name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    proc_name = None
            conns.append({
                "pid": c.pid,
                "process": proc_name,
                "local_addr": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else None,
                "remote_addr": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else None,
                "status": c.status,
            })
    except (psutil.AccessDenied, PermissionError):
        conns.append({"error": "Permissão negada — rode como administrador/root para ver todas as conexões"})
    return conns


# ---------------------------------------------------------------------------
# 3. Itens de inicialização (startup) — específico por SO
# ---------------------------------------------------------------------------
def list_startup_items():
    """Lista programas/serviços configurados para iniciar com o sistema, marcando os conhecidos."""
    if IS_WINDOWS:
        items = _list_startup_windows()
    elif IS_LINUX:
        items = _list_startup_linux()
    else:
        return [{"error": f"SO não suportado: {platform.system()}"}]

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
        items.append({"error": "winreg indisponível (execute no Windows)"})
    return items


def _list_startup_linux():
    items = []
    # systemd user/system services habilitados
    try:
        out = subprocess.run(
            ["systemctl", "list-unit-files", "--type=service", "--state=enabled"],
            capture_output=True, text=True, timeout=10
        )
        for line in out.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[0].endswith(".service"):
                items.append({"name": parts[0], "type": "systemd", "state": parts[1]})
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # crontab do usuário
    try:
        out = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
        for line in out.stdout.splitlines():
            if line.strip() and not line.strip().startswith("#"):
                items.append({"name": "cron job", "command": line.strip(), "type": "cron"})
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # autostart de apps (.desktop)
    autostart_dir = os.path.expanduser("~/.config/autostart")
    if os.path.isdir(autostart_dir):
        for f in os.listdir(autostart_dir):
            if f.endswith(".desktop"):
                items.append({"name": f, "type": "autostart-desktop", "path": os.path.join(autostart_dir, f)})

    return items


# ---------------------------------------------------------------------------
# 4. Registro de todas as tools disponíveis (formato p/ function calling)
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
            "description": "Lista os processos em execução no sistema, com uso de CPU e memória.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_network_connections",
            "description": "Lista conexões de rede ativas (TCP/UDP) e qual processo está associado a cada uma.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_startup_items",
            "description": "Lista programas, serviços e tarefas configurados para iniciar automaticamente com o sistema.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


if __name__ == "__main__":
    # Teste rápido standalone
    print(json.dumps({
        "processes_sample": list_processes(limit=5),
        "startup_items": list_startup_items()[:5],
    }, indent=2, ensure_ascii=False))
