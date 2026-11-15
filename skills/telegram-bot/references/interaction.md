---
last_updated: 2026-11-15T10-05
sources: ~/health/desks/2026-11-15-telegram-gateway/ (README, HANDOFF, PLAN, REVIEW-1..4, gateway.py, state/gateway.log.jsonl), ~/health/desks/2026-11-14-telegram-expressiveness/README.md
---

# Interaction: commands, cards, behavior, quirks

Write for Gilad with [writing-style.md](writing-style.md). This file covers how to send, and what happens after.

## Where the gateway is today

- Code and state: `~/health/desks/2026-11-15-telegram-gateway/`. It will move to `~/dev/telegram-bot`. Until then, use the paths below as written.
- The daemon `gateway.py serve` runs under launchd (`com.giladbarnea.health-telegram-gateway`, KeepAlive). Check it with `status`. Do not start a second one: a lock makes it exit.
- The daemon is the only process that polls Telegram. It talks only to Gilad's private chat. Every other sender or chat is dropped.
- The bot token is in `~/health/.env`. Never print it, log it, write it to a file or commit it.
- One gateway serves all agents. A card wakes only its owner (see the wake table).

## Commands

```sh
G="uv run ~/health/desks/2026-11-15-telegram-gateway/gateway.py"   # the only line to change after the move
$G say "$(cat <<'EOF'
## Title

**rich** markdown
EOF
)" [--silent]                       # a message, no reply expected
$G ask card.yaml                    # a question card
$G revise card.yaml                 # same id: new body or options, repainted in place
$G close <card-id> "optional note"  # collapse the card to "Closed by the agent"
$G status                           # JSON: daemon alive, cards, armed drafts, undelivered wakes, failed requests
$G placement pinned|keyboard|both   # where Send lives; default pinned. Change it only if Gilad asks
$G check "why"                      # end-to-end test: a message to Gilad, a wake to the Lead, an ntfy push
```

- Use a heredoc or `$'…'` for multi-line text. A plain `"…\n…"` in bash sends a literal backslash-n.
- `say` and `ask` bodies are rich Markdown (`sendRichMessage`), not `parse_mode` text. Follow the table, highlight and length rules in the writing style.
- Each command waits up to 15 s for the daemon's verdict. It exits non-zero with the logged error when the request failed, or when nobody picked it up. A request nobody picked up waits and runs when the daemon starts.
- Failed requests are renamed `*.failed` in `state/queue/` and logged in `state/gateway.log.jsonl` (event `request_failed`). A failed `ask` leaves no card behind. Fix the spec and ask again.
- After a timeout, run `status` before you ask again.

## Card format (`ask`, `revise`)

```yaml
id: clinic              # at most 12 characters (Telegram callback data is capped at 64 bytes)
owner: herdr-session:pi:<your PI_SESSION_ID>   # who is woken on Send; resolved to its current pane at delivery
urgency: notifying      # or silent; default notifying
body: |                 # rich Markdown; the first line is the card's title
  ## Title
  | A | B |             # at most 3 table columns
fields:                 # at most 4 single, 4 multi, 1 date
  - {id: pick, kind: single, label: Which?, options: [{id: a, label: A}, {id: b, label: B}]}
  - {id: extras, kind: multi, label: Include, options: [{id: x, label: X}]}
  - {id: day, kind: date, label: Which day?}
  - {id: note, kind: note, label: Anything else?}   # Gilad replies to the card with text, a photo or a voice note
recommended: A, because ...    # printed on the card
relations: {answers: [other-id]}   # printed on the card only; no behavior yet
```

- `owner`: use `herdr-session:pi:$PI_SESSION_ID` for yourself. Use another session's id for another agent. `herdr:<pane>` is a literal pane address and breaks when panes move. Any other value only logs, and nobody is woken.
- `recommended`: say which option you would pick and why. This is the single most useful line on a card.
- `silent` sends without a notification sound. Use it for non-urgent cards.
- `relations` (`blocked_by`, `supersedes`, `answers`) are text on the card only. Do not rely on them.
- `revise` works only on an open card. It drops armed picks that no longer exist. An answered or closed card cannot be revised or closed again: ask a new card with a new id.
- Examples: `~/health/desks/2026-11-15-telegram-gateway/cards/`.
- Card ids must be unique. They stay in use after the card is answered.
- Per the writing style, keep cards short. Split rather than stack: several small cards, one claim each.

## What Gilad does, and what wakes whom

Wakes are `herdr agent prompt` messages that start with a bracketed tag, such as `[Telegram] Gilad wrote: …` or `[Telegram batch] … Read <path>`.

| Gilad does | What happens |
|---|---|
| Taps a choice, picks a date, adds a note to a card, reacts to a card | Armed as a draft. Nobody wakes. The Outbox message lists what is armed. |
| Presses **Send** (the pinned Outbox) | One batch file per card owner in `state/batches/`. One wake per owner: `[Telegram batch] Gilad pressed Send. Read <path>`. Answered cards repaint as "✓ Answered" with his picks. |
| Sends a plain message, a photo, a voice note, a file, a forward, or replies to something that is not an open card | The Lead wakes at once, even while answers are armed. |
| Reacts to a `say` message | The Lead wakes at once with that message's text. |
| Edits a message the gateway delivered | Routed like the original and marked `[Telegram edit] … 'old' -> 'new'`. An armed, unsent note just takes the new text. An edit owed to a card owner waits for Send while answers are armed. |
| Reacts to or replies to an answered or closed card | The Lead wakes at once with the card's title. |

- The **Lead** is the Health Lead session (`GATEWAY_LEAD` in the installed plist `~/Library/LaunchAgents/com.giladbarnea.health-telegram-gateway.plist`). If you are not the Lead, you wake only through a card you own. To change the Lead: edit the installed plist, then `launchctl bootout` and `launchctl bootstrap` it (`kickstart` does not reread the plist).
- Wakes are durable. Each is written to `state/wakes.json` first, then delivered with retry and backoff (max 5 min, in order per owner). A blocked agent or a moved pane delays a wake. It does not lose it. `status` shows undelivered wakes.
- A wake stuck for 10 minutes makes the gateway tell Gilad once, by ntfy and in Telegram.
- Delivery is at least once. A crash between a delivered wake and its bookkeeping sends it again.
- **Reply in Telegram, through the gateway, not in the session, when a Telegram message woke you.** Gilad is on his phone. He will not see your session text. Use `say` for a conversational reply, or `ask` for a decision.
- When you answer a batch, say what you did with each answer. Gilad pressed Send and expects acknowledgement.

## Quirks (established with Gilad on 2026-11-15)

Each item comes from the gateway's code, its docs, its log, or Gilad's own report. Item 7 rests on Gilad's report and the gateway's subscription list (it subscribes to no deletion event). It was not checked against Telegram's documentation.

1. **Taps, notes and reactions on a card wake nobody.** They arm drafts. Only the pinned Outbox's Send wakes the card owner, once, with one batch file.
2. **Plain messages, media, edits and reactions on `say` messages wake the Lead immediately.** This includes everything that is not an open card's reply. Do not tell Gilad to "reply on the card" for a free-form answer. A note field is for a card answer. A plain message is a conversation.
3. **Replies carry the replied-to text.** The wake ends with `[reply to message N: <text>]`. A reply to a card carries only the card's title line. A reply to the Outbox carries the Outbox text. A reply to a media message with no text carries `(no text: <type>)`.
4. **Forwards carry origin and date.** The wake ends with `[forwarded from <who>, originally sent <iso time>]`. A forwarded rich message from the bot itself is read as text (tables as `a | b`).
5. **Files sent from the Files menu have no caption.** Telegram sends such a file at once, before he can type. A file attached that way arrives as a bare media message. Ask him to reply to the file with text.
6. **A reply with an attached file arrives as two unlinked messages.** The text carries the reply context. The file arrives separately with no context and no link to the text. Match them by time and ask him if it is unclear.
7. **Telegram does not report deletions in private chats.** Gilad can only delete "for me", and the bot hears nothing. A message he deleted is invisible to you. Do not infer anything from silence.
8. **The bot deletes "pinned a message" lines.** Pinning the Outbox leaves a service line in the chat. The gateway sweeps it, so the pin stays silent.
9. **The Send key on the keyboard shows only while the letter keyboard is hidden.** On iOS he reaches it with the four-dot icon. This placement (`placement keyboard|both`) is off by default. Gilad prefers the pinned Outbox, which is pinned only while something is armed. A message with a bottom keyboard cannot be edited, so that summary is a separate message.
10. **`sendWidget` is refused** (`INPUT_MEDIA_WIDGET_NOT_ALLOWED`). Do not try inline widgets. A Mini App is the escape hatch for forms too dense for chat, and is not built. A `sendPoll` attempt timed out with delivery unknown. Polls are unproven.
11. **Voice notes are Ogg/Opus.** The gateway saves them under `state/media/<message id>-<file id>` with no extension. Convert to AAC m4a, then transcribe with the meeting transcriber at its cheapest:

    ```sh
    ffmpeg -i <saved file> -c:a aac /tmp/voice.m4a
    cd ~/dev/meeting-transcriber && uv run meeting-transcriber /tmp/voice.m4a --output-directory /tmp/voice-transcript \
      --transcription-services-count 1 --no-validation
    ```

    The result is `/tmp/voice-transcript/transcript.md`. With one service it skips both the merge and the validation, so it needs no `pi`. Without these flags it runs five services and is slow and costly.

Other behavior to know:

- A file larger than 20 MB cannot be downloaded (Bot API limit). The wake says `(attachment not downloaded: <error>)` and carries the text.
- Photos, voice, documents, audio, video, video notes and animations are downloaded to `state/media/`. Location, contact and sticker wake the Lead with only their type.
- Incoming images can be read: the gateway downloads them and you can open the saved file.
- A reaction is not an approval. Never act on a reaction alone for anything real-world.
- Gilad's messages and files stay on disk (`state/gateway.log.jsonl`, `state/media/`), unpruned. This is medical data. Gilad has not decided the retention policy. Do not copy it elsewhere.

## Not built

`blocked_by` and `supersedes` behavior, pruning and rotation, a Mini App, and a move to `~/dev/telegram-bot`.

## Tests

`uv run ~/health/desks/2026-11-15-telegram-gateway/test_gateway.py` drives the gateway through a fake Telegram: no network, no token. The fake encodes what we believe about Telegram. It was wrong once, so a green run is not proof about the real thing.
