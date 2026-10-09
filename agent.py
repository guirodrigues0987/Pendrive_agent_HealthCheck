"""
agent.py - System scan agent, running 100% locally from a USB drive.

Works with any local server exposing an OpenAI-compatible API:
  - llama.cpp:  ./llama-server -m model.gguf -c 4096 --port 8080
  - Ollama:     ollama serve   (default port 11434, endpoint /v1/chat/completions)

Usage:
    python agent.py
    python agent.py --host http://localhost:11434 --model llama3

DESIGN NOTE:
Small models (7B-8B) running via llama.cpp often fail at tool-calling parsing
when they try to call several tools in the same response (known "peg-native
format" bug in llama-server). Since the scan always runs the same fixed set of
tools, there is no need to let the model "decide" which to call - Python runs
all of them directly, and the LLM is only used to interpret the raw data and
write the final summary.

It also keeps a scan history (scans/) and compares against the previous scan
to highlight only what CHANGED, and applies a whitelist (whitelist.json) to
reduce noise from processes/items already known to be normal.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

from history import diff_snapshots, load_latest_snapshot, save_snapshot
from tools import list_network_connections, list_processes, list_startup_items

SYSTEM_PROMPT = """You are a security agent that analyzes real data collected from a computer
(running processes, network connections and startup items) and writes a summary in
{language} for a non-technical person.

Important rules:
- You are NOT an antivirus and do not recognize known malware signatures. Never state
  categorically that something "is malware" or "is a known malware server" - you have no
  reputation database. At most say that something "deserves a closer look".
- Items marked "whitelisted": true are already known/expected in this kind of
  environment - do not spend time commenting on them unless something about them looks
  clearly out of the ordinary (e.g. a strange execution path for a common program).
- Pay special attention to the "WHAT CHANGED SINCE THE LAST SCAN" section when it exists -
  it is the strongest signal of something new worth investigating.
- Rely only on the data provided. Do not invent processes, connections or programs that
  are not in the list.
- If nothing looks suspicious, say so clearly - do not invent problems to seem useful.
- Be direct and concise. Do not repeat the whole data list, only highlight what matters.
"""


def call_llm(host, model, messages, timeout=1800):
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        f"{host}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"\n[ERROR] The server responded with HTTP error {e.code}.")
        print(f"Details: {body[:500]}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\n[ERROR] Could not reach the LLM server at {host}.")
        print("Check that the llama.cpp server or Ollama is running.")
        print(f"Details: {e}")
        sys.exit(1)


def _trim(data, max_chars=6000):
    return json.dumps(data, ensure_ascii=False)[:max_chars]


def build_prompt(processes, connections, startup, diff):
    sections = [
        f"RUNNING PROCESSES (top 30 by memory usage):\n{_trim(processes)}",
        f"ACTIVE NETWORK CONNECTIONS:\n{_trim(connections)}",
        f"AUTOMATIC STARTUP ITEMS:\n{_trim(startup)}",
    ]

    if diff is not None:
        changed = diff["new_processes"] or diff["new_remote_connections"] or diff["new_startup_items"]
        if changed:
            sections.append(
                "WHAT CHANGED SINCE THE LAST SCAN (relative to "
                + str(diff["previous_timestamp"])
                + "):\n"
                + json.dumps(
                    {
                        "new_processes": diff["new_processes"],
                        "new_remote_connections": diff["new_remote_connections"],
                        "new_startup_items": diff["new_startup_items"],
                    },
                    ensure_ascii=False,
                )
            )
        else:
            sections.append("WHAT CHANGED SINCE THE LAST SCAN: nothing new compared to the previous scan.")
    else:
        sections.append("This is the first recorded scan - there is no previous scan to compare against.")

    return "\n\n".join(sections)


def run_agent(host, model, language="English"):
    print("Agent started. Collecting system data...\n")

    print("  -> collecting running processes...")
    processes = list_processes(limit=30)
    print("  -> collecting network connections...")
    connections = list_network_connections()
    print("  -> collecting startup items...")
    startup = list_startup_items()

    previous = load_latest_snapshot()
    diff = diff_snapshots(previous, processes, connections, startup)

    snapshot_path = save_snapshot(processes, connections, startup)
    print(f"  -> snapshot saved at: {snapshot_path}")

    prompt_data = build_prompt(processes, connections, startup, diff)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(language=language)},
        {
            "role": "user",
            "content": (
                "Here is the data collected from my computer. Analyze it and tell me whether "
                "there is anything irregular:\n\n" + prompt_data
            ),
        },
    ]

    print("\nAnalyzing with the local model (may take 1-3 minutes)...\n")
    response = call_llm(host, model, messages)
    answer = response["choices"][0]["message"]["content"].strip()

    print("=" * 60)
    print("SCAN SUMMARY")
    print("=" * 60)
    print(answer)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="System scan agent (100% local).")
    parser.add_argument("--host", default="http://localhost:8080", help="URL of the local LLM server")
    parser.add_argument(
        "--model", default="local-model", help="Model name (Ollama requires the exact name, e.g. llama3)"
    )
    parser.add_argument("--language", default="English", help="Language of the final summary")
    args = parser.parse_args()

    run_agent(args.host, args.model, args.language)
