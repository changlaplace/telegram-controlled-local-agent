The usrname of my bot is chang_reports_agent_bot.
The display name is Reports Agent.

# Reports WAgent

A minimal Telegram frontend for a LangChain Deep Agent using DeepSeek. The agent
can inspect and edit files, run shell commands, run Python, and install packages
inside `AGENT_WORKSPACE`. Conversation checkpoints are stored in SQLite, so chat
memory survives bot restarts.

## Setup

1. In Telegram, open the verified `@BotFather` account, send `/newbot`, follow
   the prompts, and keep the bot token private.
2. Create a DeepSeek API key at <https://platform.deepseek.com/api_keys> and add
   enough API credit for model calls.
3. Create your local environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

4. Edit `.env` and set `TELEGRAM_BOT_TOKEN` and `DEEPSEEK_API_KEY`. Leave
   `TELEGRAM_ALLOWED_USER_IDS` empty for the first launch.
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
