---
name: telegram-bot
description: How to talk to Gilad through his Telegram bot (@health_gilad_bot): when to use Telegram instead of the Plannotator Inbox, how to write for it, and how to send cards, questions and messages through the gateway. Load before you send Gilad anything on Telegram, or when a Telegram message wakes you.
last_updated: 2026-11-15T10-05
---

# Telegram bot

Gilad reaches agents through a Telegram bot. A gateway daemon owns the bot. Agents never call Telegram directly.

## Read both references first

Reading both files is required. Do not skip one because the task looks small.

1. [references/writing-style.md](references/writing-style.md): how to write and format for Gilad's phone. Read it before you compose any Telegram message or card.
2. [references/interaction.md](references/interaction.md): the commands, the card format, the gateway's behavior and the quirks of Telegram. Read it before you run any gateway command, or when a `[Telegram …]` message wakes you.

## Telegram or Inbox

Default to the Plannotator Inbox. Use Telegram only when both conditions hold:

1. **Gilad is away.** You cannot see whether he reads anything. In your own Inbox threads you see only the messages he sent, and partly his drafts. Treat him as away when he has sent no Inbox message in the last 10 minutes.
2. **You need one or two decisions.** The answer must turn stopped work into resumed work. A card with a few taps fits.

Everything more serious stays in the Inbox: long reports, many questions, anything with files to review, and anything that needs thought before he answers.

When you send on Telegram, give a decision he can make in seconds. Name what waits for it.

## Pings: ntfy or Telegram

Gilad wants to try moving ntfy pings to Telegram. He has not decided. Until he decides, keep sending urgent pings with ntfy as before (see the project's AGENTS.md).

## Where the gateway is today

The gateway code and its state live in `~/health/desks/2026-11-15-telegram-gateway/`. It will move to `~/dev/telegram-bot` later. Until it moves, use the paths in `references/interaction.md` as written. After it moves, the `G=` path in that file is the only line to change.
