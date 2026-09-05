"""
history.py — Histórico de scans e comparação entre execuções.

Cada scan é salvo como um snapshot JSON em scans/, com timestamp no nome.
A cada nova execução, comparamos com o snapshot mais recente anterior para
destacar SÓ o que mudou (processo novo, item de inicialização novo, conexão
nova) — isso reduz muito o ruído e ajuda o LLM (e você) a focar no que
realmente importa, em vez de reler a mesma lista gigante toda vez.
"""

import json
import os
from datetime import datetime

SCANS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scans")


def _ensure_dir():
    os.makedirs(SCANS_DIR, exist_ok=True)


def list_snapshots():
    """Retorna os caminhos dos snapshots salvos, em ordem cronológica."""
    _ensure_dir()
    files = [f for f in os.listdir(SCANS_DIR) if f.startswith("scan_") and f.endswith(".json")]
    files.sort()
    return [os.path.join(SCANS_DIR, f) for f in files]


def load_latest_snapshot():
    """Carrega o snapshot mais recente salvo, ou None se não houver nenhum."""
    snapshots = list_snapshots()
    if not snapshots:
        return None
    with open(snapshots[-1], "r", encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(processes, connections, startup_items):
    """Salva um novo snapshot com timestamp e retorna o caminho do arquivo."""
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
    """Extrai um conjunto de nomes/identificadores de uma lista de dicts, ignorando entradas de erro."""
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
    Compara o snapshot anterior com os dados atuais e retorna um dict com o que
    é NOVO em cada categoria (apareceu agora e não estava antes).
    Se não houver snapshot anterior (primeiro scan), retorna None.
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
