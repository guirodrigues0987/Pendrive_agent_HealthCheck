"""
agent.py — Agente de scan do sistema, rodando 100% local a partir do pendrive.

Funciona com qualquer servidor local que exponha API compatível com OpenAI:
  - llama.cpp:  ./llama-server -m modelo.gguf -c 4096 --port 8080
  - Ollama:     ollama serve   (porta padrão 11434, endpoint /v1/chat/completions)

Uso:
    python agent.py
    python agent.py --host http://localhost:11434 --model llama3

DESIGN NOTE:
Modelos pequenos (7B-8B) rodando via llama.cpp costumam falhar no parsing de
tool-calling quando tentam chamar várias ferramentas na mesma resposta (bug
conhecido de "peg-native format" no llama-server). Como o scan sempre roda o
mesmo conjunto fixo de ferramentas, não há necessidade de deixar o modelo
"decidir" quais chamar — o Python roda todas diretamente, e o LLM entra só
para interpretar os dados brutos e escrever o resumo final em português.

Também mantém um histórico de scans (scans/) e compara com o anterior para
destacar só o que MUDOU, além de aplicar uma whitelist (whitelist.json) para
reduzir ruído de processos/itens já conhecidos como normais.
"""

import argparse
import json
import sys
import urllib.request
import urllib.error

from tools import list_processes, list_network_connections, list_startup_items
from history import load_latest_snapshot, save_snapshot, diff_snapshots

SYSTEM_PROMPT = """Você é um agente de segurança que analisa dados reais coletados de um
computador (processos em execução, conexões de rede e itens de inicialização) e escreve
um resumo em português para uma pessoa não técnica.

Regras importantes:
- Você NÃO é um antivírus e não reconhece assinaturas de malware conhecido. Não afirme
  categoricamente que algo "é malware" ou "é um servidor de malware conhecido" — você não
  tem base de dados de reputação. Diga no máximo que algo "merece verificação".
- Itens marcados como "whitelisted": true já são conhecidos/esperados nesse tipo de
  ambiente — não gaste tempo comentando sobre eles, a menos que algo neles pareça
  claramente fora do padrão (ex: caminho de execução estranho para um programa comum).
- Dê atenção especial à seção "O QUE MUDOU DESDE O ÚLTIMO SCAN" quando ela existir — é
  o sinal mais forte de algo novo que vale investigar.
- Baseie-se apenas nos dados fornecidos. Não invente processos, conexões ou programas
  que não estejam na lista.
- Se nada parecer suspeito, diga isso claramente — não invente problemas para parecer útil.
- Seja direto e objetivo. Não repita a lista inteira de dados, só destaque o que importa.
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
        print(f"\n[ERRO] O servidor respondeu com erro HTTP {e.code}.")
        print(f"Detalhe: {body[:500]}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\n[ERRO] Não consegui falar com o servidor LLM em {host}.")
        print("Verifique se o llama.cpp server ou o Ollama estão rodando.")
        print(f"Detalhe: {e}")
        sys.exit(1)


def _trim(data, max_chars=6000):
    return json.dumps(data, ensure_ascii=False)[:max_chars]


def build_prompt(processes, connections, startup, diff):
    sections = [
        f"PROCESSOS EM EXECUÇÃO (top 30 por uso de memória):\n{_trim(processes)}",
        f"CONEXÕES DE REDE ATIVAS:\n{_trim(connections)}",
        f"ITENS DE INICIALIZAÇÃO AUTOMÁTICA:\n{_trim(startup)}",
    ]

    if diff is not None:
        mudou_algo = diff["new_processes"] or diff["new_remote_connections"] or diff["new_startup_items"]
        if mudou_algo:
            sections.append(
                "O QUE MUDOU DESDE O ÚLTIMO SCAN (em relação a " + str(diff["previous_timestamp"]) + "):\n"
                + json.dumps({
                    "processos_novos": diff["new_processes"],
                    "conexoes_remotas_novas": diff["new_remote_connections"],
                    "itens_inicializacao_novos": diff["new_startup_items"],
                }, ensure_ascii=False)
            )
        else:
            sections.append("O QUE MUDOU DESDE O ÚLTIMO SCAN: nada de novo em relação ao scan anterior.")
    else:
        sections.append("Este é o primeiro scan registrado — não há scan anterior para comparar.")

    return "\n\n".join(sections)


def run_agent(host, model):
    print("Agente iniciado. Coletando dados do sistema...\n")

    print("  → coletando processos em execução...")
    processes = list_processes(limit=30)
    print("  → coletando conexões de rede...")
    connections = list_network_connections()
    print("  → coletando itens de inicialização...")
    startup = list_startup_items()

    previous = load_latest_snapshot()
    diff = diff_snapshots(previous, processes, connections, startup)

    snapshot_path = save_snapshot(processes, connections, startup)
    print(f"  → snapshot salvo em: {snapshot_path}")

    prompt_data = build_prompt(processes, connections, startup, diff)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            "Aqui estão os dados coletados do meu computador. Analise e me diga se "
            "tem alguma irregularidade:\n\n" + prompt_data
        )},
    ]

    print("\nAnalisando com o modelo local (pode levar 1-3 minutos)...\n")
    response = call_llm(host, model, messages)
    answer = response["choices"][0]["message"]["content"].strip()

    print("=" * 60)
    print("RESUMO DO SCAN")
    print("=" * 60)
    print(answer)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agente de scan do sistema (100% local).")
    parser.add_argument("--host", default="http://localhost:8080", help="URL do servidor LLM local")
    parser.add_argument("--model", default="local-model", help="Nome do modelo (Ollama exige o nome exato, ex: llama3)")
    args = parser.parse_args()

    run_agent(args.host, args.model)
