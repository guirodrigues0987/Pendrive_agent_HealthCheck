# Agente de Scan do Sistema — 100% local, rodando do pendrive

Agente que usa um LLM local (sem internet) para analisar processos, conexões
de rede e itens de inicialização do computador, e apontar o que parece
suspeito. **Não substitui um antivírus** — é uma camada de triagem/leitura
em linguagem natural sobre dados reais do sistema.

Funciona em Windows e Linux a partir do mesmo pendrive.

---

## 1. Estrutura de pastas no pendrive

```
pendrive/
├── agent.py
├── tools.py
├── history.py
├── whitelist.json
├── README.md
├── .gitignore
├── llm/
│   ├── windows/          <- binário do llama.cpp p/ Windows (llama-server.exe)
│   └── linux/            <- binário do llama.cpp p/ Linux (llama-server)
├── models/
│   └── modelo.gguf       <- modelo quantizado (ex: Llama-3-8B-Instruct-Q4_K_M.gguf)
├── scans/                <- histórico de scans (gerado automaticamente, não versionar)
└── python/
    └── (opcional: Python portátil, ver seção 4)
```

## 2. Baixar o motor de inferência (llama.cpp)

Baixe os binários pré-compilados direto do repositório oficial:
https://github.com/ggml-org/llama.cpp/releases

- Windows: pegue o `.zip` com `win-x64` no nome, extraia em `llm/windows/`
- Linux: pegue o `.zip` com `ubuntu-x64` (ou compile na sua máquina), extraia em `llm/linux/`

Alternativa mais simples: usar o **Ollama** (https://ollama.com), que já
resolve a parte de servidor e download de modelo automaticamente — só que
ele instala no sistema em vez de rodar 100% do pendrive. Bom para testar
rápido antes de migrar pro modo "tudo no pendrive".

## 3. Baixar o modelo

Recomendado para começar: **Llama 3 8B Instruct**, quantizado em `Q4_K_M`
(bom equilíbrio entre qualidade e tamanho, ~4.5GB).

Baixe de: https://huggingface.co/models (busque por "Llama-3-8B-Instruct-GGUF")

Salve o arquivo `.gguf` em `models/`.

> Modelos maiores (13B) cabem tranquilo nos seus 128GB, mas rodam mais devagar
> em PCs sem GPU dedicada.

## 4. Python no pendrive (opcional, mas recomendado)

Se o PC de destino não tiver Python instalado, use uma versão portátil:

- Windows: baixe o "embeddable zip" em https://www.python.org/downloads/windows/
- Linux: geralmente já vem instalado; se não, um AppImage de Python resolve

Depois, instale a única dependência externa do agente:
```
pip install psutil --target python/libs
```

## 5. Rodando

**Passo 1 — subir o servidor LLM:**

Windows:
```
llm\windows\llama-server.exe -m models\modelo.gguf -c 4096 --port 8080
```

Linux:
```
./llm/linux/llama-server -m models/modelo.gguf -c 4096 --port 8080
```

**Passo 2 — rodar o agente (em outro terminal):**
```
python agent.py --host http://localhost:8080 --model local-model
```

Se estiver usando Ollama em vez de llama.cpp:
```
python agent.py --host http://localhost:11434 --model llama3
```

## 6. Permissões

Para ver *todos* os processos e conexões de rede (não só os do seu usuário),
rode o agente com privilégios de administrador/root:

- Windows: abra o terminal como Administrador
- Linux: `sudo python agent.py ...`

## 7. Histórico de scans, diffs e whitelist

- Cada execução salva um snapshot em `scans/scan_<timestamp>.json`. A partir do
  segundo scan, o agente compara automaticamente com o snapshot anterior e
  destaca processos, conexões e itens de inicialização **novos** — isso é
  bem mais útil do que reler a mesma lista enorme toda vez.
- `whitelist.json` marca processos e itens de inicialização conhecidos como
  normais (Windows, navegadores, Python, VS Code, etc). Edite esse arquivo
  livremente para o seu ambiente — o modelo é instruído a não gastar tempo
  comentando sobre itens marcados como `whitelisted: true`.
- A pasta `scans/` não deve ir para o Git (dados do seu computador). Já está
  no `.gitignore`.

## 8. Limitações (importante)

- O agente **não reconhece malware por assinatura** — ele não tem uma lista
  de vírus conhecidos. Ele aponta o que *parece* fora do padrão, e pode errar
  (falsos positivos/negativos).
- Modelos pequenos (7B-13B) cometem mais erros de formatação nas chamadas de
  função do que modelos grandes. Se o agente travar ou repetir passos, tente
  reduzir `--steps` ou trocar para um modelo maior.
- Isto é um protótipo/portfólio — para segurança real, continue usando um
  antivírus de verdade (Defender, Malwarebytes, etc.) como camada principal.
