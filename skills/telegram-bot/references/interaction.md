---
last_updated: 2026-11-27T01-10
sources: ~/dev/telegram-bot (README.md, docs/DESIGN.md, docs/LESSONS.md, src/), live use with Gilad on 2026-11-14 and 2026-11-15
---

# Interaction: commands, cards, behavior, quirks

Write for Gilad with [writing-style.md](writing-style.md). This file covers how to send, and what happens after. The tool's full reference is `~/dev/telegram-bot/README.md`.

## Your bot

- Each project has its own bot, daemon and state. Name yours in every command: `tgbot --bot <botname> …`, or export `TGBOT_BOT=<botname>`. With more than one bot configured, a bare `tgbot` refuses to guess.
- The daemon runs under launchd (`com.giladbarnea.telegram-bot.<botname>`, KeepAlive). Check it with `status`. Do not start `serve` by hand: a lock makes it exit.
- The daemon is the only process that polls Telegram. It talks only to Gilad's private chat. Every other sender or chat is dropped.
- The token lives in the file named in `~/.telegram-bot/bots/<botname>.toml`. Never print it, log it, write it elsewhere or commit it.
- State (log, media, batches, wakes) lives in the bot's `state_dir` from that config.

## Commands

```sh
B="tgbot --bot <botname>"
$B say "$(cat <<'EOF'
## Title

**rich** markdown
EOF
)" [--silent]                       # a message, no reply expected
$B say --file report.pdf ["plain caption"] [--silent] # upload a local file as a document
$B ask card.yaml                    # a question card
$B revise card.yaml                 # same id: new body or options, repainted in place
$B close <card-id> "optional note"  # collapse the card to "Closed by the agent"
$B status                           # JSON: daemon alive, cards, armed drafts, undelivered wakes, failed requests
$B placement pinned|keyboard|both   # where Send lives; default pinned. Change it only if Gilad asks
$B check "why"                      # end-to-end test: a message to Gilad, a wake to the Lead, an ntfy push if configured
```

- The text is sent as given. Use a heredoc or `$'…'` for multi-line text: a plain `"…\n…"` in bash sends a literal backslash-n.
- `say` and `ask` bodies are rich Markdown (`sendRichMessage`), not `parse_mode` text. Follow the table, highlight and length rules in the writing style.
- Text/card commands wait up to 15 s for the daemon's verdict. It exits non-zero with the logged error when the request failed, or when nobody picked it up. A request nobody picked up waits and runs when the daemon starts. After a timeout, run `status` before you ask again.
- A failed `ask` leaves no card behind. Fix the spec and ask again.

### Send a file without touching the token

Use `tgbot --bot <botname> say --file <local-path> ["plain caption"] [--silent]`. The daemon uploads one document; the caption is plain text, not rich Markdown. The local file must contain 1–50,000,000 bytes and the caption at most 1024 UTF-16 units. See the tool's README for the full contract.

File sends print a JSON receipt with `request_id`, `outcome`, `message_id` and `error`. Exit 0 / `accepted` means Telegram returned a Message ID, **not that Gilad saw it**. Exit 1 / `refused` means local validation/cancellation or explicit API refusal. Exit 2 / `unknown` means the file might have arrived: a timeout, 5xx or empty response is not proof of failure.

**Do not automatically retry an unknown send or bypass the daemon with raw-token calls.** Run `tgbot --bot <botname> status` and find the matching `document_sends` request ID. A CLI deadline can resolve later to accepted; an interrupted attempt stays unknown across restart. If still unknown, reconcile with Gilad before deliberately creating another send. The tool never retries file sends, including rate-limit refusals.

The file command waits up to 65 s; an unclaimed request is cancelled at that deadline. It snapshots the file before queuing, and removes its upload copy after terminal processing; captions and receipts remain on disk. An older running daemon needs a restart after the tool upgrade. This command does not add file sending to a project's separate, custom gateway.

Inbox remains the default for substantial review material. Use file sending when Telegram is the agreed delivery channel, rather than treating support for files as a change in channel policy.

## Card format (`ask`, `revise`)

```yaml
id: clinic              # at most 12 characters (Telegram callback data is capped at 64 bytes)
owner: lead             # default: the Lead. Or herdr-session:<harness>:<session id> to wake another agent on Send
urgency: notifying      # or silent; default notifying
body: |                 # rich Markdown; the first line is the card's title
  ## Title
  | A | B |             # at most 3 table columns
fields:                 # at most 4 single, 4 multi, 1 date
  - {id: pick, kind: single, label: Which?, options: [{id: a, label: A}, {id: b, label: B, wakeupAgent: false}]}   # wakeupAgent: default true
  - {id: extras, kind: multi, label: Include, options: [{id: x, label: X}]}
  - {id: day, kind: date, label: Which day?}
  - {id: note, kind: note, label: Anything else?}   # Gilad replies to the card with text, a photo or a voice note
recommended: A, because ...    # printed on the card
relations: {answers: [other-id]}   # printed on the card only; no behavior
```

- `recommended`: say which option you would pick and why. This is the single most useful line on a card.
- `silent` sends without a notification sound. Use it for non-urgent cards.
- `relations` (`blocked_by`, `supersedes`, `answers`) are text on the card only. Do not rely on them.
- `revise` works only on an open card. It drops armed picks that no longer exist. A finished card's id may be reused; an open card's may not.
- `wakeupAgent: false` on an option: Gilad's pick of it is committed and shown on the answered card, but left out of your batch. If nothing else on Send is for you, you are not woken. Must be a YAML boolean (`false`, not `"false"`); `ask` and `revise` refuse anything else. Use it for options whose answer needs no agent action. Such a card still turns `answered` in `status` with no batch: do not wait on it. The flag hides picks from batches only: while armed, a pick still shows in `status` and in the Outbox text Gilad can reply to.
- Examples: `~/dev/telegram-bot/examples/cards/`.
- Per the writing style, keep cards short. Split rather than stack: several small cards, one claim each.

## What Gilad does, and what wakes whom

Wakes are `herdr agent prompt` messages that start with a bracketed tag, such as `[Telegram] Gilad wrote: …` or `[Telegram batch] … Read <path>`.

| Gilad does | What happens |
|---|---|
| Taps a choice, picks a date, adds a note to a card, reacts to a card | Armed as a draft. Nobody wakes. The Outbox message lists what is armed. |
| Presses **Send** (the pinned Outbox) | One batch file per card owner. One wake per owner: `[Telegram batch] Gilad pressed Send. Read <path>`. Answered cards repaint as "✓ Answered" with his picks. Picks of options marked `wakeupAgent: false` are left out of the batch; an owner with nothing left gets no batch and no wake. |
| Sends a plain message, a photo, a voice note, a file, a forward, or replies to something that is not an open card | The Lead wakes at once, even while answers are armed. |
| Reacts to a `say` message | The Lead wakes at once with that message's text. |
| Edits a message the gateway delivered | Routed like the original and marked `[Telegram edit] … 'old' -> 'new'`. An armed, unsent note just takes the new text. An edit owed to a card owner waits for Send while answers are armed. |
| Reacts to or replies to an answered or closed card | The Lead wakes at once with the card's title. |

- The **Lead** is the session that last ran `tgbot connect <botname>`. If you are not the Lead, you wake only through a card you own. To become the Lead, run `tgbot connect <botname>` from your pane; waiting wakes follow you.
- Wakes are durable: written to disk first, then delivered with retry and backoff. A blocked agent or a moved pane delays a wake. It does not lose it. `status` shows undelivered wakes. A wake stuck for 10 minutes makes the gateway tell Gilad once.
- Delivery is at least once. A crash between a delivered wake and its bookkeeping sends it again.
- **Reply in Telegram, through `tgbot`, not in the session, when a Telegram message woke you.** Gilad is on his phone. He will not see your session text. Use `say` for a conversational reply, or `ask` for a decision.
- When you answer a batch, say what you did with each answer. Gilad pressed Send and expects acknowledgement.

## Quirks (established with Gilad on 2026-11-15)

Each item comes from the tool's code, its docs, or Gilad's own report. The history of each is in `~/dev/telegram-bot/docs/LESSONS.md`.

1. **Taps, notes and reactions on a card wake nobody.** They arm drafts. Only the pinned Outbox's Send wakes the card owner, once, with one batch file.
2. **Plain messages, media, edits and reactions on `say` messages wake the Lead immediately.** Do not tell Gilad to "reply on the card" for a free-form answer. A note field is for a card answer. A plain message is a conversation.
3. **Replies carry the replied-to text.** The wake ends with `[reply to message N: <text>]`. A reply to a card carries only the card's title line. A reply to a media message with no text carries `(no text: <type>)`.
4. **Forwards carry origin and date.** The wake ends with `[forwarded from <who>, originally sent <iso time>]`. A forwarded rich message from the bot itself is read as text (tables as `a | b`).
5. **Files sent from the Files menu have no caption.** Telegram sends such a file at once, before he can type. Ask him to reply to the file with text.
6. **A reply with an attached file arrives as two unlinked messages.** The text carries the reply context; the file arrives separately. Match them by time and ask him if it is unclear.
7. **Telegram does not report deletions in private chats.** Gilad can only delete "for me", and the bot hears nothing. Do not infer anything from silence.
8. **The bot deletes "pinned a message" lines**, so the Outbox pin stays silent.
9. **The Send key on the keyboard shows only while the letter keyboard is hidden.** On iOS he reaches it with the four-dot icon. This placement is off by default. Gilad prefers the pinned Outbox, pinned only while something is armed.
10. **`sendWidget` is refused** (`INPUT_MEDIA_WIDGET_NOT_ALLOWED`). Do not try inline widgets. A Mini App is the escape hatch for forms too dense for chat, and is not built. Polls are unproven.
11. **Voice notes are Ogg/Opus.** They are saved under the bot's `state_dir/media/` with no extension. Convert to AAC m4a, then transcribe with the meeting transcriber at its cheapest:

    ```sh
    ffmpeg -i <saved file> -c:a aac /tmp/voice.m4a
    cd ~/dev/meeting-transcriber && uv run meeting-transcriber /tmp/voice.m4a --output-directory /tmp/voice-transcript \
      --transcription-services-count 1 --no-validation
    ```

    The result is `/tmp/voice-transcript/transcript.md`. Without these flags it runs five services and is slow and costly.

Other behavior to know:

- A file larger than 20 MB cannot be downloaded (Bot API limit). The wake says `(attachment not downloaded: <error>)` and carries the text.
- Photos, voice, documents, audio, video, video notes and animations are downloaded. Location, contact and sticker wake the Lead with only their type. You can open saved images.
- A reaction is not an approval. Never act on a reaction alone for anything real-world.
- The bot's log and media stay on disk, unpruned. Follow your project's data policy, and do not copy them elsewhere.
