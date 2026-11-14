---
name: telegram-writing-style
description: Gilad's presentation preferences for Telegram messages, cards and forms, with descriptive notes on formatting and interaction components tried. Read when composing or reviewing Telegram communication for him.
last_updated: 2026-11-14T19-27
---

# Telegram writing style

Gilad liked the rich formatting in the phone trial. The problems were density, highlighted backgrounds and long cards—not richness itself.

## Firm style constraints

- **At most three table columns.** Four were cramped on the phone. Headers and cells still need room to read naturally.
- **No highlighted-background text**, regardless of color or brightness. A dark or black highlight is not an alternative.
- **Shorter cards, split generously into individual messages.** A quiet conversation does not mean packing everything into the fewest possible bubbles.

## Components observed in the trial

These describe what was tried, not a required toolkit or instructions to choose particular APIs.

| Component | Observed implementation and result |
|---|---|
| Native rich formatting | `sendRichMessage` with `rich_message.markdown`: headings, a real table, nested lists/emphasis, `<details>`, spoilers, syntax-highlighted code, rendered task boxes, Hebrew and footnotes appeared on the iPhone. |
| Basic formatted messages | `sendMessage` with `parse_mode: HTML` carried emphasis, quotes, expandable blockquotes, spoilers and code. This is distinct from the separate rich-message Markdown mode. |
| Choice controls and changing cards | `InlineKeyboardMarkup` / `callback_data` produced `callback_query` events. `answerCallbackQuery` acknowledged taps; `editMessageReplyMarkup` changed selections and `editMessageText` changed the card in place. |
| Contextual replies | `reply_to_message` identified an older message and included its content, even after newer cards arrived. Answers did not have to follow presentation order. |
| Multi-field forms | A reply-keyboard `web_app` button opened an HTTPS Mini App built with HTML/CSS/JavaScript. `Telegram.WebApp.ready()` / `expand()` initialized it; `sendData()` returned a `Message.web_app_data` bundle. Radio choices, checkboxes, a date and a note stayed local until the form's Submit. |
| Grouped visual material | `sendMediaGroup` delivered two synthetic comparison images as an album. A requested voice reply was not received during the trial. |
| Native reactions | A later `getUpdates` read returned an actual `message_reaction` with 👍 in the private bot chat, correcting an earlier documentation-based caution about private-chat observability. |
| Incoming images | `getFile` plus the authenticated Bot API file-download route delivered a photo that the agent could view and read—not merely a file identifier. |
| Receiving responses | `getUpdates` long polling captured subscribed update types with a persisted offset and a user/chat allowlist. The bot's event capture and the AI's wake policy were separate pieces. |

## Interaction distinctions the trial exposed

A tap reaching a lightweight bot is not the same as an AI turn. The original watcher conflated them; draft-tap filtering was subsequently changed and unit-tested. A complete native cross-message draft plus canonical Send transaction was not implemented or live-proven. The Mini App's single-submission path was proven, but its Submit is not Telegram's ordinary composer Send.

A visual reaction, the person's report of reacting, and a callback from an acknowledgement button are different evidence.

Native `RichTextMarked` / Markdown `==…==` has no bot-selectable highlight color field. `sendWidget` was attempted but rejected with `INPUT_MEDIA_WIDGET_NOT_ALLOWED`; a `sendPoll` attempt timed out with delivery uncertain. Those attempts did not establish working widgets or polls.

The observations are from 2026-11-14. The [rich-message reference](https://core.telegram.org/bots/api/rich-messages), [Mini App reference](https://core.telegram.org/bots/webapps) and [Bot API changelog](https://core.telegram.org/bots/api-changelog) describe the respective surfaces; documentation alone did not prove availability for the tested bot.
