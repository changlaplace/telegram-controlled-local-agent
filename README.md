# Reports WAgent

A private Telegram frontend for a DeepSeek-powered LangChain Deep Agent on
Windows and Linux. The bot can edit files, run Python and shell commands, install packages,
use MCP tools, transcribe voice messages, and retain per-chat memory in SQLite.

Bot username: `@chang_reports_agent_bot`

Display name: `Reports Agent`

## Setup

Requirements: Windows or Linux, PowerShell or Bash, `uv`, a Telegram bot token, and a DeepSeek API
key.

1. Open the verified `@BotFather` account in Telegram, send `/newbot`, and keep
   the returned token private.
2. Create a DeepSeek API key at <https://platform.deepseek.com/api_keys>.
3. Prepare the project:

   ```bash
   uv sync
   cp .env.example .env
   ```

4. Set at least these values in `.env`:

   ```env
   TELEGRAM_BOT_TOKEN=your-token
   DEEPSEEK_API_KEY=your-key
   TELEGRAM_ALLOWED_USER_IDS=
   ```

5. Launch the agent:
   - On Windows: Double-click `start_agent.bat`
   - On Linux/macOS: Run `./start_agent.sh`
   
   Then open the bot, and send `/whoami`.
6. Put the returned numeric user ID in `TELEGRAM_ALLOWED_USER_IDS`, then
   restart the agent:
   - On Windows: Double-click `restart_agent.bat`
   - On Linux/macOS: Run `./restart_agent.sh`

Multiple allowed IDs can be comma-separated. Keep the bot private and leave
Telegram privacy mode enabled.

## MCP Configuration

The agent dynamically loads MCP servers from the environment file (`.env`) and from `mcp_servers.json` inside the `AGENT_WORKSPACE` directory.

- **Dynamic Loading**: You can ask the bot to edit `agent_workspace/mcp_servers.json` to add or remove MCP servers during a conversation. Afterward, use `/restart` to reload the tools immediately.
- **Built-in Support**: Xiaohongshu (via `XIAOHONGSHU_MCP_ENABLED`), LinkedIn, and Tavily integrations are pre-configured. Ensure the external services are running and toggle their settings in `.env`.

## Launchers

The launch scripts work without VS Code:

- `start_agent` starts one hidden supervisor and one status monitor (if display is available).
- `stop_agent` stops the complete agent process tree and leaves the monitor
  showing the stopped state.
- `restart_agent` stops and starts the agent, reloading code and config.

Using `restart_agent` as the normal launcher is fine, but it terminates any
task currently in progress. Repeated starts do not create duplicate agents or
monitors.

For foreground development only:

```powershell
uv run python main.py
```

Direct foreground launch is not supervised, so Telegram-triggered automatic
restart is unavailable in that mode.

## Telegram Commands

The startup notification, `/start`, and `/help` all show the complete list:

- `/start` shows bot status and commands.
- `/help` shows command help.
- `/whoami` shows your Telegram user and chat IDs.
- `/cancel` interrupts the current agent request without clearing memory.
- `/restart` restarts a supervised agent and loads code or configuration changes.
- `/reset` clears the current chat's saved agent history.

Messages sent quickly in the same chat are processed sequentially. Each shell
command has a 300-second timeout, and each complete agent request has a 10-minute
timeout.

## Workspace And Self-Update

Normal filesystem and shell work starts in:

```env
AGENT_WORKSPACE=./agent_workspace
```

The included Codex skill is under `agent_workspace\skills\codex-cli`. It teaches
the agent to invoke the local Codex CLI for implementation and review work.

When explicitly asked to modify the Telegram agent itself, the agent can locate
this host project through `REPORTS_WAGENT_ROOT`. A typical request is:

```text
Use Codex to update your own code. Run the relevant tests, and only after they
pass, call restart_agent to load the new version.
```

`restart_agent` is an internal agent tool, separate from the Telegram `/restart`
command. It waits until the current reply is delivered before asking the
supervisor to relaunch the bot. Changes to `supervisor.py`, BAT files, or
`agent_control.ps1` still require `restart_agent.bat` because they are outside the
restarted child process.

## Audio Transcription

Voice notes and audio files are transcribed before being sent to the agent. Every
audio-triggered reply begins with the recognized text:

```text
Transcription:
...
```

Free local multilingual transcription is the default:

```env
TRANSCRIPTION_PROVIDER=local
LOCAL_TRANSCRIPTION_MODEL=base
LOCAL_TRANSCRIPTION_DEVICE=cpu
LOCAL_TRANSCRIPTION_COMPUTE_TYPE=int8
LOCAL_TRANSCRIPTION_MODEL_DIR=./.agent_runtime/whisper_models
TRANSCRIPTION_LANGUAGE=
```

The first use downloads the Whisper model. Leave `TRANSCRIPTION_LANGUAGE` empty
for mixed Chinese and English auto-detection. `tiny` is faster but less accurate;
`small` and `medium` are slower but more accurate.

OpenAI transcription remains optional:

```env
TRANSCRIPTION_PROVIDER=openai
OPENAI_API_KEY=your-key
TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe
```

## MCP Servers

MCP loading is centralized in `reports_wagent/mcp_tools.py`. Restart the agent
after changing MCP configuration.

Tavily web search:

```env
TAVILY_API_KEY=your-key
TAVILY_MCP_URL=https://mcp.tavily.com/mcp/
TAVILY_DEFAULT_PARAMETERS={"search_depth":"basic","max_results":5}
```

LinkedIn browser automation:

```powershell
uvx mcp-server-linkedin@latest --login
```

```env
LINKEDIN_MCP_ENABLED=true
LINKEDIN_MCP_COMMAND=uvx
LINKEDIN_MCP_ARGS=["mcp-server-linkedin@latest"]
LINKEDIN_MCP_ENV={"UV_HTTP_TIMEOUT":"300"}
```

Additional MCP servers can be configured manually without changing Python code:

```env
MCP_SERVERS_JSON={"my_server":{"transport":"stdio","command":"uvx","args":["some-mcp@latest"]}}
```

The agent does not have an automatic MCP installation tool. This keeps MCP
execution and credentials under explicit configuration control.

## Runtime Files

Runtime state is kept outside `AGENT_WORKSPACE`:

- `.agent_memory/checkpoints.sqlite` stores conversation memory.
- `.agent_runtime/status.json` stores the five-minute heartbeat.
- `.agent_runtime/launcher.json` tracks supervisor and monitor processes.
- `.agent_runtime/agent.out.log` contains standard output.
- `.agent_runtime/agent.err.log` contains errors and startup diagnostics.
- `.agent_runtime/whisper_models` caches local transcription models.

## Safety

- Only IDs in `TELEGRAM_ALLOWED_USER_IDS` can invoke the agent.
- The local shell is powerful and is not an operating-system sandbox.
- MCP servers and installed packages execute with your Windows account's access.
- The agent should access its host source only when explicitly requested.
- Keep `.env`, Telegram tokens, API keys, cookies, and browser profiles private.
- Review broad, destructive, account-facing, or publishing actions before running
  them.
