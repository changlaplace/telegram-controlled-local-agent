The usrname of my bot is chang_reports_agent_bot.
The display name is Reports Agent.

# Reports WAgent

A minimal Telegram frontend for a LangChain Deep Agent using DeepSeek. The agent
can inspect and edit files, run shell commands, run Python, and install packages
inside `AGENT_WORKSPACE`. It can also use Tavily remote MCP for live web search
when `TAVILY_API_KEY` is configured, and transcribes Telegram voice/audio
messages locally by default. Conversation checkpoints are stored in SQLite, so
chat memory survives bot restarts.

## Setup

1. In Telegram, open the verified `@BotFather` account, send `/newbot`, follow
   the prompts, and keep the bot token private.
2. Create a DeepSeek API key at <https://platform.deepseek.com/api_keys> and add
   enough API credit for model calls.
3. Create your local environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

4. Edit `.env` and set `TELEGRAM_BOT_TOKEN` and `DEEPSEEK_API_KEY`. Voice/audio
   transcription runs locally by default. To enable web search, also set
   `TAVILY_API_KEY`. Leave `TELEGRAM_ALLOWED_USER_IDS` empty for the first
   launch.
5. Start the bot:

   ```powershell
   uv run python main.py
   ```

6. Open your new bot in Telegram, press **Start**, and send `/whoami`. Stop the
   local bot with `Ctrl+C`, put the returned numeric user ID in `.env`, and
   restart it. For example:

   ```env
   TELEGRAM_ALLOWED_USER_IDS=123456789
   ```

7. Send the bot a normal text message such as `Initialize a uv Python project
   here and create a hello.py script.` Use `/reset` to clear the current
   conversation.

Multiple allowed IDs can be comma-separated. Keep Telegram privacy mode enabled
and use a private chat for this local development bot.

## Current safety boundary

- Only IDs in `TELEGRAM_ALLOWED_USER_IDS` can invoke the agent.
- Filesystem tools are rooted below `AGENT_WORKSPACE`.
- Shell commands run with `AGENT_WORKSPACE` as their current working directory.
- Shell execution is local and not sandboxed. It can install packages, run
  Python, modify files, and potentially access files outside the workspace if a
  command asks it to. Only use this bot in a private chat with allowlisted users.

For package installs inside `agent_workspace`, ask the agent to use `uv init`
and `uv add <package>`.

## Audio Transcription

Telegram voice notes and audio files are transcribed before they are sent to the
agent. The bot prefixes every audio-triggered reply with:

```text
Transcription:
...
```

Local transcription is the default and does not require an API key:

```env
TRANSCRIPTION_PROVIDER=local
LOCAL_TRANSCRIPTION_MODEL=base
LOCAL_TRANSCRIPTION_DEVICE=cpu
LOCAL_TRANSCRIPTION_COMPUTE_TYPE=int8
LOCAL_TRANSCRIPTION_MODEL_DIR=./.agent_runtime/whisper_models
```

The first audio message downloads the selected Whisper model. `base` is a small,
CPU-friendly multilingual model. For better accuracy, use `small` or `medium`;
for faster but weaker transcription, use `tiny`.

OpenAI transcription is still available if you explicitly choose it:

```env
TRANSCRIPTION_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe
```

The language is auto-detected by default. To improve accuracy and latency, set
an ISO-639-1 language hint:

```env
TRANSCRIPTION_LANGUAGE=en
```

Examples include `en`, `zh`, `ja`, `ko`, `es`, `fr`, and `de`.

## Tavily MCP

Set this in `.env`:

```env
TAVILY_API_KEY=tvly-your-key
TAVILY_MCP_URL=https://mcp.tavily.com/mcp/
```

Optional defaults can be passed as JSON:

```env
TAVILY_DEFAULT_PARAMETERS={"search_depth":"basic","max_results":5}
```

Then restart the bot and ask something like `Search the web for the latest
LangChain Deep Agents MCP docs and summarize with links.`

## Expandable MCPs

MCP loading is centralized in `reports_wagent/mcp_tools.py`. Tavily, LinkedIn,
and any extra JSON-configured MCP servers are loaded together and passed to the
Deep Agent as prefixed tools.

### LinkedIn MCP

The LinkedIn MCP server uses your own browser session. Log in locally first:

```powershell
uvx mcp-server-linkedin@latest --login
```

Then enable it in `.env`:

```env
LINKEDIN_MCP_ENABLED=true
LINKEDIN_MCP_COMMAND=uvx
LINKEDIN_MCP_ARGS=["mcp-server-linkedin@latest"]
LINKEDIN_MCP_ENV={"UV_HTTP_TIMEOUT":"300"}
```

Restart the bot after enabling it. Early tool calls may need a retry while the
LinkedIn MCP server prepares its browser cache.

Use LinkedIn automation sparingly. The server controls a real browser session,
and automated LinkedIn access may violate LinkedIn's terms or restrict your
account.

### Generic MCP Servers

Add extra MCP servers without code changes:

```env
MCP_SERVERS_JSON={"my_server":{"transport":"stdio","command":"uvx","args":["some-mcp@latest"]}}
```

## Background Run

On Windows, use `Start-Process` as the `nohup`-style launcher. This starts the
agent without a visible terminal window and writes logs under `.agent_runtime`:

```powershell
$root = "C:\Users\changlaplace\Desktop\reports_wagent"
New-Item -ItemType Directory -Force "$root\.agent_runtime" | Out-Null
Start-Process `
  -FilePath "$root\.venv\Scripts\python.exe" `
  -ArgumentList "main.py" `
  -WorkingDirectory $root `
  -WindowStyle Hidden `
  -RedirectStandardOutput "$root\.agent_runtime\agent.out.log" `
  -RedirectStandardError "$root\.agent_runtime\agent.err.log"
```

Or use the batch launcher:

```powershell
.\start_agent.bat
```

This starts the hidden agent and opens the tiny status monitor. To stop it:

```powershell
.\stop_agent.bat
```

After changing `.env`, MCP settings, or code, restart the hidden agent:

```powershell
.\restart_agent.bat
```

To open only the status monitor:

```powershell
Start-Process `
  -FilePath "$root\.venv\Scripts\pythonw.exe" `
  -ArgumentList "monitor.py" `
  -WorkingDirectory $root
```

The monitor reads `AGENT_STATUS_FILE`, which defaults to:

```env
AGENT_STATUS_FILE=./.agent_runtime/status.json
```

To stop the hidden agent:

```powershell
$status = Get-Content "$root\.agent_runtime\status.json" | ConvertFrom-Json
Stop-Process -Id $status.pid
```

## Codex CLI Skill

The Deep Agent loads project skills from:

```text
agent_workspace\skills
```

The included `codex-cli` skill teaches it how to invoke the local Codex CLI with
`codex exec`, model selection, review mode, and goal-oriented prompts.

After changing skills, restart the bot. If an existing Telegram thread does not
notice the new skill, send `/reset` once.
