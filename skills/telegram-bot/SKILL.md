---
name: telegram-bot
description: How to interact with Gilad through Telegram. Load this when Telegram communication starts.
last_updated: 2026-11-17T15-25
---

# Telegram bot

Gilad reaches the Lead of each project through that project's own Telegram bot. The generic tool `tgbot` (repo `~/dev/telegram-bot`) runs one daemon per bot. Agents never call Telegram directly.

## Read both references first

Reading both files is required. Do not skip one because the task looks small.

1. [references/writing-style.md](references/writing-style.md): how to write and format for Gilad's phone. Read it before you compose any Telegram message or card.
2. [references/interaction.md](references/interaction.md): the commands, the card format, what wakes whom, and the quirks of Telegram. Read it before you run any `tgbot` command, or when a `[Telegram …]` message wakes you.

## Connect your project's bot

When Gilad says "I set up a bot for this project: <botname>. Its keys are in <place>. Connect to it":

1. `tgbot init <botname> --env-file <place> --user-name Gilad` (add `--token-key` if the key is not `TELEGRAM_BOT_TOKEN`). Without `--chat-id`, it asks Gilad to press Start in the bot.
2. `tgbot connect <botname>`, from your own pane. It registers you as the Lead, starts the bot's launchd job, and proves a real round trip.
3. Reply "Done, <botname> is connected", and confirm you know the three things in this skill: when to use Telegram, how to write for it, and which interactions exist.

Configuration and every command: `~/dev/telegram-bot/README.md`.

## Telegram or Inbox

Default to the Plannotator Inbox. Use Telegram only when both conditions hold:

1. **Gilad is away.** You cannot see whether he reads anything. In your own Inbox threads you see only the messages he sent, and partly his drafts. Treat him as away when he has sent no Inbox message in the last 10 minutes.
2. **You need one or two decisions.** The answer must turn stopped work into resumed work. A card with a few taps fits.

Everything more serious stays in the Inbox: long reports, many questions, files needing substantial review, and anything that needs thought before he answers. When Telegram is the agreed file-delivery channel, use `tgbot say --file`; the interaction reference explains receipts and unknown outcomes. Never handle the bot token or automatically retry an unknown file send.

When you send on Telegram, give a decision he can make in seconds. Name what waits for it.

## Pings: ntfy or Telegram

Gilad wants to try moving ntfy pings to Telegram. He has not decided. Until he decides, keep sending urgent pings with ntfy as before (see the project's AGENTS.md).
