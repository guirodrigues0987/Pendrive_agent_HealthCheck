# System Scan Agent - 100% local, runs from a USB drive

[![CI](https://github.com/guirodrigues0987/Pendrive_agent_HealthCheck/actions/workflows/ci.yml/badge.svg)](https://github.com/guirodrigues0987/Pendrive_agent_HealthCheck/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

An agent that uses a local LLM (no internet) to analyze a computer's processes,
network connections and startup items, and point out what looks suspicious.
**It is not a replacement for antivirus software** - it is a triage layer that
explains real system data in natural language.

It works on Windows and Linux from the same USB drive.

Architecture diagrams live in the companion repository
[pendrive-agent-docs](https://github.com/guirodrigues0987/pendrive-agent-docs).

---

## 1. Folder layout on the USB drive

```
pendrive/
├── agent.py
├── tools.py
├── history.py
├── whitelist.json
├── README.md
├── .gitignore
├── llm/
│   ├── windows/          <- llama.cpp binary for Windows (llama-server.exe)
│   └── linux/            <- llama.cpp binary for Linux (llama-server)
├── models/
│   └── model.gguf        <- quantized model (e.g. Llama-3-8B-Instruct-Q4_K_M.gguf)
├── scans/                <- scan history (generated automatically, do not version)
└── python/
    └── (optional: portable Python, see section 4)
```

## 2. Download the inference engine (llama.cpp)

Download the prebuilt binaries from the official repository:
https://github.com/ggml-org/llama.cpp/releases

- Windows: get the `.zip` with `win-x64` in the name and extract it to `llm/windows/`
- Linux: get the `.zip` with `ubuntu-x64` (or build it on your machine) and extract it to `llm/linux/`

A simpler alternative is **Ollama** (https://ollama.com), which handles the server
and model download automatically - but it installs on the system instead of
running 100% from the USB drive. Good for a quick test before moving to the
"everything on the USB drive" mode.

## 3. Download the model

Recommended to start with: **Llama 3 8B Instruct**, quantized as `Q4_K_M`
(good balance between quality and size, ~4.5GB).

Download it from https://huggingface.co/models (search for "Llama-3-8B-Instruct-GGUF")
and save the `.gguf` file in `models/`.

> Larger models (13B) fit comfortably on a 128GB drive, but run slower on PCs
> without a dedicated GPU.

## 4. Python on the USB drive (optional but recommended)

If the target PC has no Python installed, use a portable version:

- Windows: download the "embeddable zip" from https://www.python.org/downloads/windows/
- Linux: usually preinstalled; otherwise a Python AppImage works

Then install the agent's only external dependency:

```
pip install -r requirements.txt --target python/libs
```

## 5. Running

**Step 1 - start the LLM server:**

Windows:
```
llm\windows\llama-server.exe -m models\model.gguf -c 4096 --port 8080
```

Linux:
```
./llm/linux/llama-server -m models/model.gguf -c 4096 --port 8080
```

**Step 2 - run the agent (in another terminal):**
```
python agent.py --host http://localhost:8080 --model local-model
```

If you are using Ollama instead of llama.cpp:
```
python agent.py --host http://localhost:11434 --model llama3
```

The summary is written in English by default; use `--language "Portuguese"` (or any
other language) to change it.

## 6. Permissions

To see *all* processes and network connections (not only your user's), run the
agent with administrator/root privileges:

- Windows: open the terminal as Administrator
- Linux: `sudo python agent.py ...`

## 7. Scan history, diffs and whitelist

- Each run saves a snapshot to `scans/scan_<timestamp>.json`. From the second
  scan on, the agent automatically compares with the previous snapshot and
  highlights **new** processes, connections and startup items - far more useful
  than re-reading the same huge list every time.
- `whitelist.json` marks processes and startup items known to be normal
  (Windows, browsers, Python, VS Code, etc). Edit it freely for your
  environment - the model is told not to spend time commenting on items marked
  `whitelisted: true`.
- The `scans/` folder must not go to Git (data from your computer). It is
  already in `.gitignore`.

## 8. Development

```
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for commit conventions.

## 9. Limitations (important)

- The agent **does not recognize malware by signature** - it has no list of
  known viruses. It points out what *looks* out of the ordinary and can be wrong
  (false positives/negatives).
- Small models (7B-13B) make more formatting mistakes in function calls than
  large models. If the analysis looks unreliable, try switching to a larger model.
- This is a prototype/portfolio project - for real security, keep using a real
  antivirus (Defender, Malwarebytes, etc.) as the main layer.

## License

[MIT](LICENSE)
