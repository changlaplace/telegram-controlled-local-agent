from __future__ import annotations

import asyncio
import json
import logging
import os
from asyncio import Task
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from reports_wagent.agent import AgentService
from reports_wagent.config import ConfigurationError, Settings
from reports_wagent.transcription import (
    TranscriptionService,
    audio_payload_from_message,
)

LOGGER = logging.getLogger(__name__)
TELEGRAM_MESSAGE_LIMIT = 4000
STATUS_HEARTBEAT_SECONDS = 300


def _thread_id(update: Update) -> str:
    chat = update.effective_chat
    user = update.effective_user
    if chat is None or user is None:
        raise ValueError("Update has no effective chat or user")
    return f"telegram:{chat.id}:{user.id}"


def _is_allowed(update: Update, settings: Settings) -> bool:
    user = update.effective_user
    return user is not None and user.id in settings.allowed_user_ids


def _chunks(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    text = text.strip()
    if not text:
        return ["The agent returned an empty response."]

    chunks: list[str] = []
    while len(text) > limit:
        split_at = text.rfind("\n", 0, limit + 1)
        if split_at < limit // 2:
            split_at = text.rfind(" ", 0, limit + 1)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()
    if text:
        chunks.append(text)
    return chunks


async def _reply(update: Update, text: str) -> None:
    message = update.effective_message
    if message is None:
        return
    for chunk in _chunks(text):
        await message.reply_text(chunk)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    user = update.effective_user
    if user is None:
        return
    access = "enabled" if _is_allowed(update, settings) else "locked"
    await _reply(
        update,
        "Deep Agent bot is online.\n"
        f"Your Telegram user ID: {user.id}\n"
        f"Agent access: {access}\n\n"
        "Send a text request to work with the agent. Commands: /whoami, "
        "/reset, /help",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(
        update,
        "Send a text message to ask the agent to inspect or edit workspace files.\n"
        "/whoami - show your Telegram user ID\n"
        "/reset - clear this chat's saved agent history\n"
        "/help - show this message",
    )


async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if user is None or chat is None:
        return
    await _reply(update, f"User ID: {user.id}\nChat ID: {chat.id}")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if not _is_allowed(update, settings):
        await _reply(update, "Agent access is locked for this user. Use /whoami.")
        return
    service: AgentService = context.application.bot_data["agent_service"]
    await service.reset(_thread_id(update))
    await _reply(update, "Conversation history cleared.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if not _is_allowed(update, settings):
        await _reply(
            update,
            "Agent access is locked for this user. Use /whoami, add that user ID "
            "to TELEGRAM_ALLOWED_USER_IDS, and restart the bot.",
        )
        return

    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None or not message.text:
        return

    await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)
    service: AgentService = context.application.bot_data["agent_service"]
    try:
        answer = await service.ask(_thread_id(update), message.text)
    except Exception:
        LOGGER.exception("Agent request failed for user %s", update.effective_user.id)
        await _reply(
            update,
            "The agent request failed. Check the local bot logs and your DeepSeek "
            "API key or account balance.",
        )
        return
    await _reply(update, answer)


async def handle_audio_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if not _is_allowed(update, settings):
        await _reply(
            update,
            "Agent access is locked for this user. Use /whoami, add that user ID "
            "to TELEGRAM_ALLOWED_USER_IDS, and restart the bot.",
        )
        return

    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None:
        return

    transcription_service: TranscriptionService | None = (
        context.application.bot_data.get("transcription_service")
    )
    if transcription_service is None:
        await _reply(
            update,
            "Audio transcription is disabled. Set TRANSCRIPTION_PROVIDER=local "
            "or TRANSCRIPTION_PROVIDER=openai in .env and restart the bot.",
        )
        return

    await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)
    try:
        payload = await audio_payload_from_message(message)
        if payload is None:
            return
        transcript = await transcription_service.transcribe(payload)
        service: AgentService = context.application.bot_data["agent_service"]
        answer = await service.ask(_thread_id(update), transcript)
    except Exception:
        LOGGER.exception(
            "Audio agent request failed for user %s", update.effective_user.id
        )
        await _reply(
            update,
            "The audio request failed. Check the local bot logs, OPENAI_API_KEY, "
            "and your OpenAI account balance.",
        )
        return

    await _reply(update, _with_transcription(transcript, answer))


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOGGER.exception("Unhandled Telegram update error", exc_info=context.error)


def build_application(settings: Settings) -> Application:
    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .concurrent_updates(4)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.bot_data["settings"] = settings
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("whoami", whoami))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(
        MessageHandler(filters.VOICE | filters.AUDIO, handle_audio_message)
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_error_handler(error_handler)
    return application


async def post_init(application: Application) -> None:
    settings: Settings = application.bot_data["settings"]
    settings.agent_memory_db.parent.mkdir(parents=True, exist_ok=True)
    memory_context = AsyncSqliteSaver.from_conn_string(str(settings.agent_memory_db))
    checkpointer = await memory_context.__aenter__()
    application.bot_data["memory_context"] = memory_context
    tools = await _load_tavily_tools(settings)
    application.bot_data["agent_service"] = AgentService(settings, checkpointer, tools)
    if settings.transcription_provider != "off":
        application.bot_data["transcription_service"] = TranscriptionService(settings)
    status_task = application.create_task(_write_status_loop(settings))
    application.bot_data["status_task"] = status_task


async def post_shutdown(application: Application) -> None:
    settings: Settings = application.bot_data["settings"]
    status_task: Task[None] | None = application.bot_data.get("status_task")
    if status_task is not None:
        status_task.cancel()
    memory_context: AbstractAsyncContextManager[AsyncSqliteSaver] | None = (
        application.bot_data.get("memory_context")
    )
    if memory_context is not None:
        await memory_context.__aexit__(None, None, None)
    _write_status(settings, "stopped")


async def _load_tavily_tools(settings: Settings) -> list[BaseTool]:
    if settings.tavily_api_key is None:
        LOGGER.info("TAVILY_API_KEY is not set; Tavily MCP web tools are disabled.")
        return []

    headers = {"Authorization": f"Bearer {settings.tavily_api_key}"}
    if settings.tavily_default_parameters:
        headers["DEFAULT_PARAMETERS"] = json.dumps(settings.tavily_default_parameters)

    client = MultiServerMCPClient(
        {
            "tavily": {
                "transport": "streamable_http",
                "url": settings.tavily_mcp_url,
                "headers": headers,
            }
        },
        tool_name_prefix=True,
    )
    tools = await client.get_tools(server_name="tavily")
    LOGGER.info("Loaded %d Tavily MCP tool(s).", len(tools))
    return tools


async def _write_status_loop(settings: Settings) -> None:
    try:
        _write_status(settings, "running")
        while True:
            await asyncio.sleep(STATUS_HEARTBEAT_SECONDS)
            _write_status(settings, "running")
    except asyncio.CancelledError:
        _write_status(settings, "stopped")
        raise


def _write_status(settings: Settings, state: str) -> None:
    payload: dict[str, Any] = {
        "state": state,
        "pid": os.getpid(),
        "updated_at": datetime.now(UTC).isoformat(),
        "workspace": str(settings.agent_workspace),
        "memory_db": str(settings.agent_memory_db),
        "model": settings.deepseek_model,
        "tavily_mcp": bool(settings.tavily_api_key),
        "allowed_users": len(settings.allowed_user_ids),
    }
    _write_json_atomic(settings.agent_status_file, payload)


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _with_transcription(transcript: str, answer: str) -> str:
    return f"Transcription:\n{transcript}\n\n{answer}"


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc

    if not settings.allowed_user_ids:
        LOGGER.warning(
            "TELEGRAM_ALLOWED_USER_IDS is empty; agent requests are locked. "
            "Use /whoami to discover your ID."
        )
    LOGGER.info(
        "Starting Telegram bot with model %s, workspace %s, memory DB %s, and Tavily MCP %s",
        settings.deepseek_model,
        settings.agent_workspace,
        settings.agent_memory_db,
        "enabled" if settings.tavily_api_key else "disabled",
    )
    build_application(settings).run_polling(drop_pending_updates=True)
