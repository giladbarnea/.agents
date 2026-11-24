---
description: Bank Hapoalim - log in, read account data, and transfer money to known beneficiaries.
last_updated: 2026-11-24
---

# Bank Hapoalim

Precondition: a real Chrome process is exposed on CDP `:9222` and **may** already be logged in to Bank Hapoalim. If it is not, `scripts/poalim.py login` logs in by itself with the macOS Keychain item `bankhapoalim.co.il`.

Use `scripts/poalim.py` for all of it. It drives the user's real Chrome on CDP `:9222` and reuses one bank tab across invocations.

## 1. Log in

```bash
scripts/poalim.py login                  # no-op if a session is already live
```

The credentials are a generic password in the login Keychain: service `bankhapoalim.co.il`, account = the bank username, password = the bank password. The `security` CLI created it, so `security find-generic-password` reads it without a prompt. No Bitwarden and no human are needed (since 2026-11-24). If the bank password changes, update the item from Bitwarden once: `security add-generic-password -U -s bankhapoalim.co.il -a <username> -w <password>`, never echoing the values. `login` exits before typing anything if the item is missing or empty, so a broken item never burns a failed login attempt.

Form hooks on `login.bankhapoalim.co.il/ng-portals/auth/he/`: `input#userCode`, `input#password`, and a `button[type=submit]` whose text is `כניסה`. Success is `location.href` containing `/ng-portals/rb/`. If it does not arrive, print the page text before retrying - the bank shows the reason there, and repeated blind attempts lock the account.

## 2. Read account data

The portal is a thin Angular client over a plain JSON API at `https://login.bankhapoalim.co.il/ServerServices/...`. Fetch those paths in-page with `credentials: 'include'` and parse JSON. Do not scrape the DOM for data - it is slower, fragile, and truncated by lazy rendering.

```bash
scripts/poalim.py accounts               # labels plus their API accountIds
scripts/poalim.py switch משפחה           # switch the portal to that account
scripts/poalim.py tx 12-681-643943 20260101 20260910 --grep רינת
scripts/poalim.py get "/ServerServices/current-account/composite/balanceAndCreditLimit?partyCurrentAccount=12-681-643943&lang=he"
```

The account switcher shows `681-643943`, but the API needs the bank prefix: `accountId=12-681-643943`. To find an unknown endpoint, enable `Network` over CDP, navigate to the page that shows the data, and keep the request URLs containing `ServerServices`.

Current-account transactions come from `/ServerServices/current-account/transactions` with `retrievalStartDate` and `retrievalEndDate` as `YYYYMMDD`. Each call is capped, so page by quarter and merge. Transfers carry the counterparty in `beneficiaryDetailsData.partyName`, with `eventActivityTypeCode` 2 for money out and 1 for money in. History reaches back roughly one year, no further.

Privacy guardrail: report dates, amounts, and beneficiary names. Do not print full account numbers beyond the `accountId` needed to make the call.

## 3. Transfers

Use this for recurring transfer requests to `רומי` or `רינת`. This workflow stops on the confirmation step. Do not click the final approval/send action unless the user explicitly confirms that final action at action time.

### Defaults

| Beneficiary | Default amount | Source account |
| --- | ---: | --- |
| `רומי` | 450 NIS | `שלי פרטי` |
| `רינת` | 450 NIS | `משפחה משותף` |

If the beneficiary is neither `רומי` nor `רינת`, ask which source account to use. If the user specifies an amount, use that amount. If the user asks for the recurring/default payment without an amount, use the default amount above.

### Use the script

`scripts/poalim.py` does this route. The caller always names the source account.

```bash
poalim.py transfer --from family --to רינת --amount 1350 --comment "Aug 11, 17; Sep 2"
poalim.py send      # separate command, run only on explicit approval
```

`transfer` stops on the confirmation step and sends nothing. `send` is the only thing that moves money.

The confirmation step times out after a few minutes and the wizard drops back to step 1. If `send` reports it is not on the confirmation step, run `transfer` again and then `send` promptly.

### The SMS code: hand off to a fast fork

`send` opens a "חיזוק הזדהות" dialog with five boxes, `תו 1` to `תו 5`. The SMS code expires after about 10 seconds. A large model at high thinking is too slow for the round trip.

1. Run `transfer`, and check the form.
2. Fork yourself, keeping your context, to a quicker mid-tier model at medium thinking: a Claude forks to Sonnet, a GPT forks to Terra (`openai-codex/gpt-6.1-terra`). The fork has one task: run `send`, ask the user for the code on whatever channel is active at the moment of the fork: the direct chat or the Plannotator Inbox. Not Telegram: forks cannot listen on the main thread there. The fork then types the code, confirm, and report the `אסמכתא` or the bank's exact error.
3. Direct chat: give the fork a visible pane (for example `showOnHerdrPane`), and tell the user to type the code there. Inbox: the Inbox delivers a reply to the session that wrote the message, so a fork that asks in the thread gets the code itself (verified 26-11-16).
4. Allow one code attempt only. Repeated wrong codes lock the account. Type the code with real input. On 26-11-13 a JavaScript click on `המשך` failed, while a real click works.

Verified on 26-11-16: a Sonnet medium fork paid on the first code.

### Narrow Route

Follow this by hand only if the script fails.

1. Open or reuse the transfer form.
   - From the homepage, click the right-sidebar action `העברת כסף`.
   - From a completed transfer screen, click `בצע העברה נוספת`.
   - If already on `https://login.bankhapoalim.co.il/ng-portals/rb/he/current-account/transfer` at the details step, continue in place.

2. Set the source account **from the homepage**, before opening the transfer form.
   - The account switcher is `disabled` on the transfer page. It cannot be changed once the form is open.
   - Go to the homepage, click the switcher (the button whose `aria-label` contains `בחר חשבונות`), and pick the account.
   - Then open the transfer form and check the switcher still shows the account you picked.
   - Select `שלי פרטי` for `רומי`.
   - Select `משפחה משותף` for `רינת`.

3. Fill the beneficiary.
   - Click the combobox with placeholder `למי ברצונך להעביר את הכסף?`.
   - Clear it and type the beneficiary name. The field filters the dropdown; use this instead of relying on the unfiltered list, because `רינת` is not necessarily in the initially rendered options.
   - Click the visible option containing the beneficiary name.
   - Bank, branch, and account fields autofill. Verify they filled, but do not echo account numbers into the transcript.

4. Fill the amount.
   - Click the amount input with placeholder `הזנת סכום`.
   - Clear it and enter the requested/default amount.
   - Leave the date unchanged unless the user asked otherwise.

5. Fill the comment, only if the user gave one.
   - This is the optional field with placeholder `סיבה להעברה (רשות)`, shown on the confirmation screen and stored as `beneficiaryDetailsData.messageDetail`.
   - The form labels it **maximum 17 characters**. Trust that label. Punctuation works, Hebrew and Latin both work.
   - Do not probe the limit with the input's `ng-invalid` class. It only flips at 34 characters, so it does not track the real rule and will let an over-long comment through.
   - If the user's text is too long, use their stated fallback. Do not invent a shortening.

6. Click `המשך`.
   - Stop on the `אישור` step, shown by `שלב נוכחי 2 מתוך 3`.
   - Verify the confirmation page shows the intended source account, beneficiary, and amount.
   - Do not click the final transfer button without explicit final confirmation.

## Technical Notes

Prefer raw CDP for this workflow when working against the user's already-open Chrome. In this environment, `agent-browser --cdp 9222 tab` and `agent-browser --cdp 9222 get url` exposed only an `about:blank` automation tab, not the existing Bank Hapoalim tab. The `agent-browser` CLI would be cleaner if it can be made to target the live bank tab, but verify that first; do not assume it has attached to the logged-in tab.

Raw CDP attachment pattern:

1. `GET http://localhost:9222/json/list`.
2. Pick the `type: "page"` target whose `url` contains `bankhapoalim.co.il`.
3. `GET http://localhost:9222/json/version` and connect to the browser-level `webSocketDebuggerUrl`.
4. Call `Target.attachToTarget` with `{"targetId": "...", "flatten": true}` and send all later commands with the returned `sessionId`.

Stable DOM hooks observed on the transfer page:

| Purpose | Hook |
| --- | --- |
| Source-account dropdown | `button` with `aria-label` containing `בחר חשבונות`, or visible text containing `מס'` / current account label |
| Source-account choices | visible option text: `שלי פרטי`, `משפחה משותף` |
| Beneficiary field | `input[placeholder="למי ברצונך להעביר את הכסף?"]`, `type="search"`, `role="combobox"` |
| Beneficiary dropdown | `ngb-typeahead-window`; options are `button[role="option"]` |
| Amount field | `input[placeholder="הזנת סכום"]` |
| Comment field | `input[placeholder="סיבה להעברה (רשות)"]`; max 17 chars per the form label, punctuation allowed |
| Continue button | enabled `button` with exact visible text `המשך` |
| Confirmation step | any `aria-label` containing `שלב נוכחי 2 מתוך 3` |
| Final transfer button | `button.btn3` whose text is exactly `אישור העברה`; match exactly, the wizard header holds an `<a>` reading just `אישור` |
| Source-account switcher on the transfer page | `disabled`; set the account from the homepage instead |
| Completed transfer screen | any `aria-label` containing `שלב נוכחי 3 מתוך 3`; restart link text `בצע העברה נוספת` |

The beneficiary dropdown is a typeahead. Click the beneficiary input, clear it, type the intended beneficiary name, wait until a `button[role="option"]` contains that name, and click that option. Do not scan the unfiltered list: it is long, only partly rendered, and `רינת` may not appear in the initial DOM.

Use CDP mouse clicks rather than DOM `.click()` for the bank UI. The UI is Angular/typeahead-heavy; real mouse and keyboard events matched the visible browser behavior reliably. After each page-changing click, poll for the next expected hook instead of sleeping blindly.

Privacy guardrail: do not print or persist account numbers from autofilled bank/branch/account fields. It is enough to verify that the fields are non-empty and that the confirmation screen contains the intended beneficiary, amount, and source account.
