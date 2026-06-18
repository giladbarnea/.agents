---
description: Narrow operational route for recurring Bank Hapoalim transfers to known beneficiaries.
last_updated: 2026-06-18
---

# Bank Hapoalim Transfers

Use this for recurring Bank Hapoalim transfer requests to `רומי` or `רינת`.

Precondition: a real Chrome process is already logged in to Bank Hapoalim and exposed on CDP `:9222`. Work against the existing logged-in tab. This workflow stops on the confirmation step; do not click the final approval/send action unless the user explicitly confirms that final action at action time.

## Defaults

| Beneficiary | Default amount | Source account |
| --- | ---: | --- |
| `רומי` | 450 NIS | `שלי פרטי` |
| `רינת` | 400 NIS | `משפחה משותף` |

If the beneficiary is neither `רומי` nor `רינת`, ask which source account to use. If the user specifies an amount, use that amount. If the user asks for the recurring/default payment without an amount, use the default amount above.

## Narrow Route

1. Open or reuse the transfer form.
   - From the homepage, click the right-sidebar action `העברת כסף`.
   - From a completed transfer screen, click `בצע העברה נוספת`.
   - If already on `https://login.bankhapoalim.co.il/ng-portals/rb/he/current-account/transfer` at the details step, continue in place.

2. Set the source account before choosing the beneficiary.
   - Click the account dropdown at the top of the transfer page, the button whose visible text starts with `מס'`.
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
   - Leave date and optional transfer reason unchanged unless the user asked otherwise.

5. Click `המשך`.
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
| Continue button | enabled `button` with exact visible text `המשך` |
| Confirmation step | any `aria-label` containing `שלב נוכחי 2 מתוך 3` |
| Completed transfer screen | any `aria-label` containing `שלב נוכחי 3 מתוך 3`; restart link text `בצע העברה נוספת` |

The beneficiary dropdown is a typeahead. Click the beneficiary input, clear it, type the intended beneficiary name, wait until a `button[role="option"]` contains that name, and click that option. Do not scan the unfiltered list: it is long, only partly rendered, and `רינת` may not appear in the initial DOM.

Use CDP mouse clicks rather than DOM `.click()` for the bank UI. The UI is Angular/typeahead-heavy; real mouse and keyboard events matched the visible browser behavior reliably. After each page-changing click, poll for the next expected hook instead of sleeping blindly.

Privacy guardrail: do not print or persist account numbers from autofilled bank/branch/account fields. It is enough to verify that the fields are non-empty and that the confirmation screen contains the intended beneficiary, amount, and source account.
