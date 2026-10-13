---
description: Maccabi Online doctor requests, prescription renewal, and bloodwork referrals.
last_updated: 2026-10-08
---

# Maccabi Online Doctor Requests

Use this for prescription renewal, bloodwork referrals, `לבקש חידוש מרשמים`, or similar Maccabi medical-admin actions.

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

## Bloodwork Referrals (verified 2026-10-08)

1. Follow prescription-route steps 1–4 above to select the doctor.
   - If the homepage hides the request button, open `פעולות מהירות` first.
2. Choose `הפניה לבדיקות וטיפולים`, then `לבדיקות וטיפולים`.
   - The intermediate screen asks `לאיזה צורך ההפניה?`. Do not wait for a text field before answering it.
3. Fill `פירוט הבדיקה המבוקשת`.
   - Maccabi asks which test is needed, why, and who recommended it.
   - The field allows **250 characters**. This doctor-referral flow has **no attachment option**, including at final confirmation.
   - For an expired referral, include its number and date. If the test names exceed the limit, include every exact test code from the PDF instead. Verify the codes against the PDF before submitting.
   - Separate test codes with a comma and space, or put one code on each line. Preserve leading zeros. Shorten the prose, not the separators, to fit the limit. Count spaces and line breaks as characters.
   - Write dates as `DD.MM.YYYY`. Slashes trigger the special-character validation error.
4. Click `המשך`, then `המשך ללא הוספת נושא`.
   - Switching to `שאלה בנושא אחר` does not increase the text allowance. Its field is `פירוט השאלה`, also limited to 250 characters, with no upload control on the observed question form.
5. Review `סיכום הבקשה שלך` and stop at `אישור ושליחת הבקשה` for user approval.
   - After `עריכה` → `המשך`, the flow returns directly to this summary. It does not repeat the add-topic screen.
   - The service states a response time of up to **5 business days** for family doctors.

### Laboratory attendance (checked 2026-10-08)

Source: [Maccabi laboratory guidance](https://www.maccabi4u.co.il/eligibilites/20763/).

- For adult bloodwork with a valid Maccabi referral, no appointment is needed outside the South district. South-district residents book through `*3555`.
- TSH, vitamin B12, and folic acid are morning-only tests. Check the chosen laboratory's collection hours and test availability.
- Bring a Maccabi card. The observed referral also requires an identity card for HIV testing.
- Read the new referral's preparation instructions. Do not treat an expired referral's fasting or medication restrictions as current medical advice.

### Semen-test booking (checked 2026-10-08)

- Use the laboratory's [booking page](https://lee.co.il/b/6652df3c2c6ef?source=2&tab=meetings). Select the branch explicitly. For Yigal Alon, choose `יגאל אלון 96B תא - בדיקת זרע מלאה קופ''ח`, not private testing or `השבחת זרע`. The insured test lists ₪0.
- [The laboratory website](https://www.gametalab.com/) has a Form 17 instructions page. Its Maccabi-specific block says no Form 17 is needed, only the doctor's referral. Insurer logos identify these blocks and disappear in plain-text extraction. The booking description confirms the Maccabi exception.
- The Yigal Alon branch page advertises a collection room and free sterile cups. The booking description instead instructs home collection within one hour of the appointment. Confirm room availability with the laboratory before planning on-site collection.
- If `check` reports success but the service remains unchecked, click its visible heading and verify the selected-service summary. Date selection is step 2 of 3. Do not book without the user's chosen date, time, and final approval.

## Browser Lessons (2026-10-08)

- Start at `https://online.maccabi4u.co.il/`. The bare `https://mac.maccabi4u.co.il/` returned HTTP 500 and a blank page. The Online URL supplies the login redirect.
- Public `www.maccabi4u.co.il` guidance pages do not prove login. Verify the personal-account homepage URL and the user's name. An SMS-code screen means login is incomplete.
- Take a fresh snapshot after each transition. Wait for observed screen text, not guessed field labels or a textarea. New requests and edits have different transitions, as noted above.
- Wait for the service-directory page to render before extracting text. On 2026-10-08, `get text body` on an unrendered page exposed bootstrap data, including authentication tokens and unrelated family details. After an expected heading appears in the snapshot, use `eval 'document.body.innerText'` to read visible text instead.
- Verify the exact textbox value after replacement and the exact saved text in the confirmation summary. On 2026-10-08, `fill` reported success but appended text to a populated referral field and truncated it at 250 characters. Neither `Meta+a` nor `Control+a` selected the text in that run. Do not continue until the replacement matches the intended draft.
- Search-result links can open another tab. An unchanged source tab or `ERR_ABORTED` does not prove that no result page opened. Check task-owned tabs before retrying navigation.
- Use an explicit URL read for public guidance, without opening a visible research tab:
  `agent-browser --session <task> read https://www.maccabi4u.co.il/eligibilites/20763/`
- Keep the account tab in a named, pinned session. If `tab_gone` occurs, bind a new task-owned tab rather than taking over an unrelated tab.
- Wait for a closing modal's overlay to disappear before the next action. If a sticky header covers a known button, `focus @ref` followed by `press Enter` worked for the help and back controls. Verify the resulting screen.

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
agent-browser --session maccabi --cdp 9222 --pin-tab get url
agent-browser --session maccabi --cdp 9222 --pin-tab snapshot -i -c
```

Always verify `get url` and the snapshot before acting. If `agent-browser --cdp 9222` attaches to the wrong tab, stale daemon/session state may be the reason. Run `agent-browser doctor --offline --quick` and kill only the listed `agent-browser` daemon PID for that session. Do **not** use `pkill -f agent-browser`: the real Chrome command line can include `~/.agent-browser/custom-debug-profile`, so a broad pattern can accidentally kill the logged-in CDP Chrome.

If multiple Maccabi tabs exist, especially PDF tabs under `AppointmentOrderAPI/.../pdf`, verify target selection carefully. Do not close tabs you did not open. Raw CDP against `/json/list` remains a reliable fallback: pick the `type: "page"` target whose URL contains the intended Maccabi route, connect to its `webSocketDebuggerUrl` with `suppress_origin=True`, and use real mouse clicks or `agent-browser` once targeting is corrected.
