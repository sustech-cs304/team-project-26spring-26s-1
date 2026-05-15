# OpenCrab Backend

This branch contains the OpenCrab FastAPI backend and local agent runtime. It provides conversation APIs, tool execution, task scheduling, file/RAG workflows, calendar integration, notifications, Skills Hub integration, and local SQLite persistence.

## Prerequisites

- Python 3.13.x
- uv is recommended for dependency management
- Valid model/service credentials for the providers configured in `config.yaml`

## Install

```bash
uv sync
```

Alternative with `pip`:

Windows PowerShell:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configure

Create `config.yaml` in this branch root. Keep real API keys local and out of Git.

Required top-level sections:

- `api`: model, embedding, reranking, and ASR providers.
- `file`: upload path, RAG workspace path, and file parsing provider.
- `webfetch` and `websearch`: external web tool services used by the agent.

Optional top-level sections:

- `onebot` and `telegram`: IM integrations.
- `rag_cloud`: cloud knowledge-base sync.
- `skills_cloud`: Skills Hub integration and local skill storage.
- `notification`: desktop notification behavior.
- `code_interpreter`: local code execution defaults.
- `mcp`: additional MCP tool servers.

<details>
<summary>Complete config template</summary>

```yaml
api:
  agent:
    type: OpenAI
    base_url: https://api.example.com/v1
    api_key: replace-me
    model: gpt-4.1
    max_token_count: 128000
  utility:
    type: OpenAI
    base_url: https://api.example.com/v1
    api_key: replace-me
    model: gpt-4.1-mini
    max_token_count: 128000
  embed:
    type: OpenAI
    base_url: https://api.example.com/v1
    api_key: replace-me
    model: text-embedding-3-large
    dims: 3072
  rerank:
    type: OpenAI
    base_url: https://api.example.com/v1
    api_key: replace-me
    model: rerank-model
  asr:
    type: Qwen
    base_url: wss://dashscope.aliyuncs.com/api-ws/v1/inference/
    api_key: replace-me

file:
  upload_path: ./uploads
  rag_path: ./workspace/rag
  mineru:
    base_url: https://mineru.example.com/api/v1/agent
    api_key: replace-me

webfetch:
  base_url: http://127.0.0.1:8326
  api_key: replace-me
  path: /api/fetch
  timeout_ms: 30000

websearch:
  base_url: http://127.0.0.1:8326
  api_key: replace-me
  path: /api/search
  timeout_ms: 30000

onebot:
  access_token: ""
  superuser_ids: []
  command_trigger: /agent
  message_trigger: /

telegram:
  token: ""
  superuser_ids: []
  command_trigger: /agent
  message_trigger: /

rag_cloud:
  base_url: ""
  manifest_path: /manifest.json
  timeout_ms: 30000
  api_key: ""

skills_cloud:
  base_url: ""
  timeout_ms: 30000
  delete_submission_path: ""
  local_store_path: ./workspace/skills

notification:
  enabled: true
  app_name: OpenCrab
  app_icon: assets/opencrab.png
  notification_limit: 8
  default_timeout_s: 10
  deeplink_scheme: opencrab

code_interpreter:
  default_timeout_s: 10.0
  auto_approve_max_risk_level: Low

mcp:
  example_server:
    url: http://127.0.0.1:9000/mcp
    token: null
    enabled_by_default: false
```

</details>

Configuration notes:

- `api.agent` is the main model used for agent conversations.
- `api.utility` is used for helper tasks such as lightweight generation or summarization.
- `api.embed` and `api.rerank` are used by retrieval workflows.
- `file.upload_path`, `file.rag_path`, `skills_cloud.local_store_path`, and runtime folders are local writable directories.
- Leave optional integrations blank when they are not needed.
- Replace every `replace-me` value before running features that depend on that provider.

## Run

```bash
uv run python -m agent.main --host 127.0.0.1 --port 8000
```

## Test

```bash
uv run pytest
```

## Runtime Data

The backend stores local data in SQLite databases and runtime folders such as `uploads/`, `workspace/`, `runs/`, and `cron/`. These files are local development/runtime data and should not be committed.
