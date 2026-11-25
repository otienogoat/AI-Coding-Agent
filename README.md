# AI Coding Agent

A terminal-based AI coding assistant. It talks to any OpenAI-compatible API
(OpenRouter by default), streams responses into a Rich terminal UI, and can
read, search, edit and run code in your project through a set of sandboxed
tools.

## Features

- **Streaming chat** with token accounting and automatic context compaction
- **Built-in tools**: `read_file`, `write_file`, `edit`, `apply_patch`,
  `shell`, `list_dir`, `grep`, `glob`, `web_search`, `web_fetch`, `todos`,
  `memory`
- **Subagents** for isolated codebase investigation and code review
- **MCP servers** (stdio and SSE/HTTP) loaded from config
- **Hooks** that run shell commands before/after the agent and each tool call
- **Approval policies** so destructive actions can require confirmation
- **Loop detection** to stop the model repeating itself
- **Session persistence** and checkpointing

## Requirements

- Python 3.10+ (developed with 3.11)
- An OpenRouter API key: <https://openrouter.ai/keys>

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

# Copy .env.example to .env and fill in your key
cp .env.example .env
```

`.env`:

```dotenv
OPENROUTER_API_KEY=sk-or-...
# Optional, defaults to the OpenRouter endpoint
BASE_URL=https://openrouter.ai/api/v1
```

## Usage

```bash
python main.py                       # interactive prompt
python main.py "Explain this repo"   # one-shot prompt
python main.py -c path/to/project "Fix the failing test"
```

## Project structure

```
AI-Coding-Agent/
├── main.py                 # CLI entry point
├── agent/
│   ├── agent.py            # Agent loop and lifecycle
│   ├── session.py          # Session state and LLM client wiring
│   ├── events.py           # Event types yielded to the UI
│   └── persistence.py      # Session and checkpoint storage
├── client/
│   ├── llm_client.py       # OpenAI-compatible streaming client
│   └── response.py         # Stream/response data models
├── config/
│   ├── config.py           # Pydantic config models
│   └── loader.py           # Global + project config merging
├── context/
│   ├── manager.py          # Conversation context and pruning
│   ├── compaction.py       # Summarisation when context is full
│   └── loop_detector.py    # Repeated-action detection
├── hooks/
│   └── hook_sytem.py       # Hook runner (note the historical filename)
├── prompts/
│   └── system.py           # System and compression prompts
├── safety/
│   └── approval.py         # Approval policies and command safety
├── tools/
│   ├── base.py             # Tool base classes
│   ├── registry.py         # Tool registry and invocation pipeline
│   ├── discovery.py        # Loads user tools from .ai-agent/tools
│   ├── subagents.py        # Subagent tool definitions
│   ├── builtin/            # Built-in tools
│   └── mcp/                # MCP client, manager and tool adapter
├── ui/
│   └── tui.py              # Rich terminal UI
├── utils/
│   ├── errors.py
│   ├── paths.py
│   └── text.py             # Token counting / truncation
└── scripts/
    └── test_tool.py        # Sample hook script
```

## Configuration

Configuration is TOML, merged from two places:

1. **Global** — `~/.ai-agent/config.toml`
2. **Project** — `<project>/.ai-agent/config.toml` (overrides global)

A project file also enables per-project hooks and MCP servers. Example:

```toml
[model]
name = "nvidia/nemotron-3-ultra-550b-a55b:free"

hooks_enabled = true

[[hooks]]
name = "lint"
trigger = "after_tool"
command = "python scripts/lint.py"

[mcp_servers.filesystem]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "C:/path/to/project"]
```

Note: Windows paths in TOML basic strings must be escaped (`"C:\\Users\\..."`)
or written as literal strings (`'C:\Users\...'`).

### Approval policies

Set `approval` in the config file:

| Policy       | Behaviour                                                        |
| ------------ | ---------------------------------------------------------------- |
| `on-request` | Confirm destructive or out-of-project actions (default)          |
| `on-failure` | Same as above, but only ask after a tool fails                   |
| `auto-edit`  | Auto-approve edits inside the project, confirm everything else   |
| `auto`       | Auto-approve project edits, still refuse dangerous commands      |
| `never`      | Never prompt; unsafe commands are rejected                       |
| `yolo`       | Approve everything                                               |

Commands on the built-in blocklist (`rm -rf /`, `mkfs`, disk tools, etc.) are
always rejected.

### Hooks

Hooks receive context through environment variables such as
`AI_AGENT_TRIGGER`, `AI_AGENT_TOOL_NAME` and `AI_AGENT_TOOL_ARGS`. Supported
triggers: `before_agent`, `after_agent`, `before_tool`, `after_tool`,
`on_error`.

## Environment variables

| Variable             | Required | Description                        |
| -------------------- | -------- | ---------------------------------- |
| `OPENROUTER_API_KEY` | Yes      | API key for the model provider.    |
| `BASE_URL`           | No       | Override the API base URL.         |

## Notes

- `config/loader.py` contains `AGENT_HOME_OVERRIDE`, which pins the global
  `.ai-agent` directory to a fixed home path. Set it to `None` to use the
  current OS user's home directory.
- `hooks/hook_sytem.py` keeps its original filename (sic) for import
  compatibility.
