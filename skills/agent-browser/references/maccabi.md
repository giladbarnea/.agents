---
description: Narrow operational route for renewing prescriptions on Maccabi Online.
last_updated: 2026-06-21
---

# Maccabi Online Medication Renewal

Use this when the user asks to renew meds, renew prescriptions, `לבקש חידוש מרשמים`, or similar Maccabi medical-admin actions.

Precondition: a real Chrome process is already logged in to Maccabi and exposed on CDP `:9222`. Start from `https://online.maccabi4u.co.il/`. Verify the browser is on a Maccabi tab before acting.

This workflow can submit a medical request. Stop at `אישור ושליחת הבקשה` unless the user explicitly confirms the final send action at action time.

## Narrow Route: Renew Prescriptions

1. Open or reuse Maccabi Online.
   - Open `https://online.maccabi4u.co.il/`.
   - A logged-in session lands under `/sonline/homepage/NotificationAndUpdates/`.
   - Verify the page contains `ערב טוב`, the user's name, and the quick action `בקשות מהמשרד או מהרופא/ה`.

2. Start a new doctor/office request.
   - Click the quick-action card/button `בקשות מהמשרד או מהרופא/ה`.
   - Wait for `/sonline/communicationWithDoctor/NewRequest/` and the heading `איך אפשר לעזור?`.

3. Choose the doctor request path.
   - Click `שליחת בקשה לרופא/ה בנושאים:`.
   - The card body includes `חידוש מרשם, אישור מחלה, שאלה לרופא/ה, סיכום מצב רפואי והפניה`.
   - Wait for `/sonline/communicationWithDoctor/NewRequest/Doctor` and `למי לשלוח את הבקשה?`.

4. Choose the recipient.
   - Prefer the personal doctor card when its `+ בקשה חדשה` button is enabled.
   - Known fork: `דר' אבי רונן` is often unavailable. If the personal doctor card says `הרופא לא נמצא כרגע. אפשר לשלוח בקשות החל מתאריך ...` and its `+ בקשה חדשה` button is disabled, click the enabled `+ בקשה חדשה` on the card immediately below: `צוות הרופאים/ות במרפאה של דר' אבי רונן`.
   - Wait for `/sonline/communicationWithDoctor/NewRequest/Doctor/Request` and `באיזה נושא הבקשה מהצוות הרפואי?` or equivalent.

5. Choose the prescription subject.
   - Click `חידוש ובקשת מרשם`.
   - If the modal `מומלץ לחדש את כל המרשמים יחד` appears, click `הבנתי, תודה`.

6. Ask which medications to renew.
   - The fixed-medications section is headed `תרופות קבועות`.
   - There may be a checkbox `בחירת כל המרשמים הקבועים`.
   - Ask the user whether to renew all fixed prescriptions or only specific meds.
   - In the observed run, `בחירת כל המרשמים הקבועים` selected `ATTENT 20MG X 30`, `LAMODEX 200MG X 30`, and `PAXXET 30MG X 30`.

7. Continue without adding another topic unless the user asked otherwise.
   - Click `המשך` after selecting meds.
   - If asked whether to add another topic, click `המשך ללא הוספת נושא` for medication-renewal-only requests.

8. Stop at final confirmation.
   - The confirmation screen shows `מרשם לתרופה`, `עריכה`, `מחיקה`, a `טלפון נייד` field, and `אישור ושליחת הבקשה`.
   - Verify the request summary and phone field look reasonable.
   - Do not click `אישור ושליחת הבקשה` without explicit final user confirmation.

## Stable Hooks

| Purpose | Hook |
| --- | --- |
| Entry URL | `https://online.maccabi4u.co.il/` |
| Logged-in homepage | URL contains `/sonline/homepage/NotificationAndUpdates/`; text contains `ערב טוב` |
| Quick action | Button/card text `בקשות מהמשרד או מהרופא/ה` |
| New request page | URL contains `/sonline/communicationWithDoctor/NewRequest/`; text `איך אפשר לעזור?` |
| Doctor request card | Link text starts `שליחת בקשה לרופא/ה בנושאים:` and contains `חידוש מרשם` |
| Recipient page | Text `למי לשלוח את הבקשה?` |
| Personal doctor unavailable | Text `הרופא לא נמצא כרגע. אפשר לשלוח בקשות החל מתאריך` and disabled `+ בקשה חדשה` |
| Fallback recipient | Text `צוות הרופאים/ות במרפאה של דר' אבי רונן`; enabled `+ בקשה חדשה` |
| Prescription subject | Button text `חידוש ובקשת מרשם` |
| Renewal-together modal | Heading `מומלץ לחדש את כל המרשמים יחד`; button `הבנתי, תודה` |
| Fixed meds | Heading `תרופות קבועות`; checkbox `בחירת כל המרשמים הקבועים` |
| Add-topic bypass | Button `המשך ללא הוספת נושא` |
| Final send | Button `אישור ושליחת הבקשה` |

## Technical Notes

Prefer `agent-browser` once it is attached to the right Chrome target:

```bash
agent-browser --session maccabi --cdp 9222 get url
agent-browser --session maccabi --cdp 9222 snapshot -i -c
```

Always verify `get url` and the snapshot before acting. If `agent-browser --cdp 9222` attaches to the wrong tab, stale daemon/session state may be the reason. Run `agent-browser doctor --offline --quick` and kill only the listed `agent-browser` daemon PID for that session. Do **not** use `pkill -f agent-browser`: the real Chrome command line can include `~/.agent-browser/custom-debug-profile`, so a broad pattern can accidentally kill the logged-in CDP Chrome.

If multiple Maccabi tabs exist, especially PDF tabs under `AppointmentOrderAPI/.../pdf`, close irrelevant tabs or verify target selection carefully. Raw CDP against `/json/list` remains a reliable fallback: pick the `type: "page"` target whose URL contains the intended Maccabi route, connect to its `webSocketDebuggerUrl` with `suppress_origin=True`, and use real mouse clicks or `agent-browser` once targeting is corrected.
