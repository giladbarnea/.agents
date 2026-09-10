#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["websocket-client", "requests"]
# ///
"""Base actions for Bank Hapoalim: log in, switch account, read data.

Drives the user's real Chrome over CDP :9222 and reuses one bank tab across
invocations (target id cached next to this script).

    ./poalim.py login              # log in using the Bitwarden entry
    ./poalim.py accounts           # list accounts, print their API accountIds
    ./poalim.py switch משפחה       # switch the portal to a named account
    ./poalim.py get "/ServerServices/current-account/transactions?..."
    ./poalim.py tx 12-681-643943 20260101 20260910
    ./poalim.py transfer --from family --to רינת --amount 1350 --comment "Aug 11, 17; Sep 2"
    ./poalim.py send               # separate, deliberate act: actually transfer

`get` is the general one: any ServerServices path, fetched in-page with the
live session cookies. `tx` is the current-account shorthand.
"""
import argparse
import json
import re
import os
import subprocess
import sys
import tempfile
import time

import requests
import websocket

PORT = 9222
STATE = os.path.join(tempfile.gettempdir(), "poalim-target.json")  # cache, not repo state
LOGIN_URL = "https://login.bankhapoalim.co.il/ng-portals/auth/he/?reqName=getLogonPage"
BW_ENTRY = "bankhapoalim.co.il"


class Tab:
    """A CDP session attached to one Chrome tab, via the browser-level socket."""

    def __init__(self, target_id: str):
        version = requests.get(f"http://localhost:{PORT}/json/version", timeout=10).json()
        self.ws = websocket.create_connection(
            version["webSocketDebuggerUrl"], suppress_origin=True, timeout=60
        )
        self._next_id = 0
        self.target_id = target_id
        self.session_id = self._send("Target.attachToTarget", {"targetId": target_id, "flatten": True})["sessionId"]

    def _send(self, method: str, params: dict | None = None, session_id: str | None = None) -> dict:
        self._next_id += 1
        message_id = self._next_id
        message = {"id": message_id, "method": method, "params": params or {}}
        if session_id:
            message["sessionId"] = session_id
        self.ws.send(json.dumps(message))
        deadline = time.time() + 60
        while time.time() < deadline:
            reply = json.loads(self.ws.recv())
            if reply.get("id") != message_id:
                continue
            if "error" in reply:
                raise RuntimeError(f"{method} failed: {reply['error']}")
            return reply.get("result", {})
        raise TimeoutError(method)

    def call(self, method: str, params: dict | None = None) -> dict:
        return self._send(method, params, self.session_id)

    def evaluate(self, expression: str, await_promise: bool = False):
        result = self.call("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": await_promise,
            "userGesture": True,
        })
        if "exceptionDetails" in result:
            raise RuntimeError(json.dumps(result["exceptionDetails"], ensure_ascii=False)[:800])
        return result.get("result", {}).get("value")

    def url(self) -> str:
        return self.evaluate("location.href")

    def text(self) -> str:
        return self.evaluate("document.body ? document.body.innerText : ''") or ""

    def wait_for(self, js_predicate: str, timeout: int = 45) -> bool:
        """Poll a JS predicate until true. Never sleep blindly on this SPA."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.evaluate(f"!!({js_predicate})"):
                    return True
            except Exception:
                pass
            time.sleep(0.7)
        return False

    def click(self, js_element_expression: str) -> None:
        """Real mouse click on the element returned by a JS expression.

        The Angular UI ignores synthetic .click() in places, so dispatch mouse
        events at the element's centre instead.
        """
        box_js = f"""(() => {{
          const el = ({js_element_expression});
          if (!el) return null;
          el.scrollIntoView({{block: 'center'}});
          const r = el.getBoundingClientRect();
          return {{x: r.x, y: r.y, w: r.width, h: r.height}};
        }})()"""
        box = self.evaluate(box_js)
        if not box:
            raise RuntimeError(f"no element for: {js_element_expression}")
        time.sleep(0.25)
        box = self.evaluate(box_js)
        x, y = box["x"] + box["w"] / 2, box["y"] + box["h"] / 2
        self.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "button": "none"})
        for event_type in ("mousePressed", "mouseReleased"):
            self.call("Input.dispatchMouseEvent",
                      {"type": event_type, "x": x, "y": y, "button": "left", "clickCount": 1})
            time.sleep(0.05)

    def type_text(self, text: str) -> None:
        self.call("Input.insertText", {"text": text})

    def fetch_json(self, path: str):
        """GET a ServerServices path in-page, with the live session cookies."""
        js = f"""(async () => {{
          const r = await fetch({json.dumps(path)}, {{credentials: 'include'}});
          const body = await r.text();
          return JSON.stringify({{status: r.status, body: body}});
        }})()"""
        envelope = json.loads(self.evaluate(js, await_promise=True))
        if envelope["status"] != 200:
            raise RuntimeError(f"HTTP {envelope['status']} for {path}: {envelope['body'][:300]}")
        return json.loads(envelope["body"])


def list_targets() -> list[dict]:
    return requests.get(f"http://localhost:{PORT}/json/list", timeout=10).json()


def attach(create_url: str | None = None) -> Tab:
    """Reuse our cached bank tab, else any bank tab, else open one."""
    target_id = None
    if os.path.exists(STATE):
        cached = json.load(open(STATE)).get("targetId")
        if any(t["id"] == cached for t in list_targets()):
            target_id = cached
    if not target_id:
        for target in list_targets():
            if target.get("type") == "page" and "bankhapoalim" in target.get("url", ""):
                target_id = target["id"]
                break
    if not target_id:
        if not create_url:
            raise SystemExit("no Bank Hapoalim tab open; run `poalim.py login` first")
        version = requests.get(f"http://localhost:{PORT}/json/version", timeout=10).json()
        ws = websocket.create_connection(version["webSocketDebuggerUrl"], suppress_origin=True, timeout=30)
        ws.send(json.dumps({"id": 1, "method": "Target.createTarget", "params": {"url": create_url}}))
        while True:
            reply = json.loads(ws.recv())
            if reply.get("id") == 1:
                target_id = reply["result"]["targetId"]
                break
        ws.close()
    json.dump({"targetId": target_id}, open(STATE, "w"))
    return Tab(target_id)


def bitwarden_credentials() -> tuple[str, str]:
    """Read the bank login from Bitwarden.

    Uses `bw get username/password`, not `bw get item | jq`: item JSON can carry
    raw control characters in notes and breaks jq, which silently yields empty
    credentials and burns a login attempt.
    """
    env = dict(os.environ)
    if "BW_SESSION" not in env:
        raise SystemExit("BW_SESSION is not set; unlock Bitwarden first")

    def bw(field: str) -> str:
        out = subprocess.run(["bw", "get", field, BW_ENTRY], capture_output=True, text=True, env=env)
        if out.returncode != 0:
            raise SystemExit(f"bw get {field} failed: {out.stderr.strip()[:200]}")
        return out.stdout.strip()

    return bw("username"), bw("password")


ACCOUNT_BUTTON = ("[...document.querySelectorAll('button')]"
                  ".find(e => (e.getAttribute('aria-label')||'').includes('בחר חשבונות') && e.getClientRects().length)")


def wait_ready(tab: Tab, timeout: int = 60) -> None:
    """Wait for the portal header to render, not merely for the URL to change.

    The URL flips to /ng-portals/rb/ well before the account switcher exists, so
    gating on the URL alone makes the next command fail on a missing button.
    """
    if not tab.wait_for(f"!!({ACCOUNT_BUTTON})", timeout=timeout):
        raise SystemExit("portal header did not render; is the session still live?")


def command_login(_args) -> None:
    tab = attach(create_url=LOGIN_URL)
    if "/ng-portals/rb/" in (tab.url() or ""):
        wait_ready(tab)
        print("already logged in:", tab.url())
        return
    tab.call("Page.navigate", {"url": LOGIN_URL})
    if not tab.wait_for("document.querySelector('#userCode')", timeout=45):
        raise SystemExit("login form did not render")
    time.sleep(1)

    username, password = bitwarden_credentials()
    tab.click("document.querySelector('#userCode')")
    time.sleep(0.3)
    tab.evaluate("document.querySelector('#userCode').value = ''")
    tab.type_text(username)
    time.sleep(0.3)
    tab.click("document.querySelector('#password')")
    time.sleep(0.3)
    tab.type_text(password)
    time.sleep(0.4)

    lengths = tab.evaluate(
        "JSON.stringify({user: document.querySelector('#userCode').value.length,"
        " pass: document.querySelector('#password').value.length})")
    print("filled field lengths:", lengths)

    tab.click("[...document.querySelectorAll('button')]"
              ".find(e => e.type === 'submit' && e.innerText.trim() === 'כניסה' && e.getClientRects().length)")
    if not tab.wait_for("location.href.includes('/ng-portals/rb/')", timeout=60):
        print("still on the login page. Page text:\n", tab.text()[:1200])
        raise SystemExit("login did not complete (wrong credentials, or a second factor is waiting)")
    wait_ready(tab)
    print("logged in:", tab.url())


def read_account_options(tab: Tab) -> list[str]:
    return json.loads(tab.evaluate(
        """JSON.stringify([...document.querySelectorAll('li,button,[role=option],a,div,span')]
             .filter(e => e.getClientRects().length)
             .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
             .filter(t => /^\\d{3}-\\d+ \\S/.test(t)))"""))


def command_accounts(_args) -> None:
    tab = attach()
    wait_ready(tab)
    tab.click(ACCOUNT_BUTTON)
    time.sleep(2)
    seen = []
    for label in read_account_options(tab):
        if label not in seen:
            seen.append(label)
    tab.click(ACCOUNT_BUTTON)  # close the dropdown again
    for label in seen:
        number = label.split(" ", 1)[0]
        print(f"{label}\taccountId=12-{number}")


def command_switch(args) -> None:
    tab = attach()
    wait_ready(tab)
    tab.click(ACCOUNT_BUTTON)
    time.sleep(2)
    matches = [label for label in read_account_options(tab) if args.name in label]
    if not matches:
        raise SystemExit(f"no account matching {args.name!r}; run `poalim.py accounts`")
    label = matches[0]
    tab.click(f"""(() => {{
      const els = [...document.querySelectorAll('li,button,[role=option],a,div,span')]
        .filter(e => e.getClientRects().length && (e.innerText||'').replace(/\\s+/g,' ').trim() === {json.dumps(label)});
      return els[els.length - 1];
    }})()""")
    marker = json.dumps(label.split(" ", 1)[1])
    if not tab.wait_for(f"{ACCOUNT_BUTTON} && {ACCOUNT_BUTTON}.innerText.includes({marker})", timeout=30):
        raise SystemExit(f"account did not switch to {label}")
    number = label.split(" ", 1)[0]
    print(f"switched to {label}\taccountId=12-{number}")


HOMEPAGE_URL = "https://login.bankhapoalim.co.il/ng-portals/rb/he/homepage"
TRANSFER_URL = "https://login.bankhapoalim.co.il/ng-portals/rb/he/current-account/transfer"

# The caller always names the source account. Never infer it from the beneficiary,
# and never use whichever account the portal happens to be showing.
SOURCE_ACCOUNTS = {"self": "שלי פרטי", "family": "משפחה משותף"}

COMMENT_MAX_CHARS = 17          # the form states this limit; the input's ng-invalid class does not track it
BENEFICIARY_FIELD = "document.querySelector('#nameOfBeneficiary')"
AMOUNT_FIELD = "document.querySelector('#amountToTransfer')"
COMMENT_FIELD = "document.querySelector('input[placeholder=\"סיבה להעברה (רשות)\"]')"
STEP_2 = ("[...document.querySelectorAll('*')]"
          ".some(e => (e.getAttribute('aria-label')||'').includes('שלב נוכחי 2 מתוך 3'))")
STEP_3 = ("[...document.querySelectorAll('*')]"
          ".some(e => (e.getAttribute('aria-label')||'').includes('שלב נוכחי 3 מתוך 3'))")

# Match the exact text: the wizard header also holds an <a> reading just 'אישור'.
FINAL_BUTTON = ("[...document.querySelectorAll('button')]"
                ".find(e => e.innerText.replace(/\\s+/g,' ').trim() === 'אישור העברה'"
                " && !e.disabled && e.getClientRects().length)")


def refill(tab: Tab, selector: str, text: str) -> None:
    tab.click(selector)
    time.sleep(0.3)
    tab.evaluate(f"{selector}.value = ''")
    tab.type_text(text)
    time.sleep(0.5)


def redact(text: str) -> str:
    """Strip account-number-shaped runs before printing a bank screen."""
    text = re.sub(r"\d{2}-\d{2,3}-\d{5,}", "[account]", text)
    return re.sub(r"\b\d{6,}\b", "[account]", text)


def command_transfer(args) -> None:
    """Fill the transfer form and stop on the confirmation step. Sends nothing."""
    if args.comment and len(args.comment) > COMMENT_MAX_CHARS:
        raise SystemExit(
            f"comment is {len(args.comment)} characters, the form allows {COMMENT_MAX_CHARS}. "
            "Ask the user for a shorter one; do not shorten it yourself.")

    tab = attach()
    # The account switcher is disabled on the transfer page, so the source
    # account has to be set from the homepage before the form is opened.
    tab.call("Page.navigate", {"url": HOMEPAGE_URL})
    wait_ready(tab)
    command_switch(argparse.Namespace(name=SOURCE_ACCOUNTS[args.source]))

    tab.call("Page.navigate", {"url": TRANSFER_URL})
    if not tab.wait_for(f"{BENEFICIARY_FIELD}", timeout=60):
        raise SystemExit("transfer form did not render")
    time.sleep(2)

    account_label = tab.evaluate(f"({ACCOUNT_BUTTON}).innerText.replace(/\\s+/g,' ').trim()")
    if SOURCE_ACCOUNTS[args.source] not in account_label:
        raise SystemExit(f"source account is {account_label!r}, expected {SOURCE_ACCOUNTS[args.source]!r}")
    print(f"source account: {account_label}")

    # The beneficiary list is a typeahead. Filter it by typing; do not scan the
    # unfiltered list, which is long and only partly rendered.
    refill(tab, BENEFICIARY_FIELD, args.to)
    option = (f"[...document.querySelectorAll('button[role=option]')]"
              f".find(e => e.innerText.includes({json.dumps(args.to)}))")
    if not tab.wait_for(f"!!({option})", timeout=20):
        raise SystemExit(f"no beneficiary option matching {args.to!r}")
    tab.click(option)
    time.sleep(2.5)

    autofilled = tab.evaluate("""JSON.stringify(['#bank-list', '#branch-list', '#details-account-number']
      .map(s => !!(document.querySelector(s) || {}).value))""")
    if "false" in autofilled:
        raise SystemExit("bank/branch/account did not autofill for this beneficiary")

    refill(tab, AMOUNT_FIELD, str(args.amount))
    if args.comment:
        refill(tab, COMMENT_FIELD, args.comment)

    state = tab.evaluate(f"""JSON.stringify({{
      beneficiary: {BENEFICIARY_FIELD}.value,
      amount: {AMOUNT_FIELD}.value,
      date: document.querySelector('#transferDate').value,
      comment: {COMMENT_FIELD}.value
    }})""")
    print("form:", state)

    tab.click("[...document.querySelectorAll('button')]"
              ".find(e => e.innerText.replace(/\\s+/g,' ').trim() === 'המשך' && !e.disabled && e.getClientRects().length)")
    if not tab.wait_for(STEP_2, timeout=45):
        print(redact(tab.text())[:1500])
        raise SystemExit("did not reach the confirmation step")

    print("\n--- confirmation (nothing sent yet) ---")
    print(redact(tab.text())[:1800])
    print("\nTo transfer, run: poalim.py send")


def command_send(_args) -> None:
    """Click the final transfer button. Only ever run this on explicit approval."""
    tab = attach()
    if not tab.evaluate(STEP_2):
        raise SystemExit("not on the confirmation step; the wizard times out, so run `transfer` again first")
    tab.click(FINAL_BUTTON)
    if not tab.wait_for(STEP_3, timeout=60):
        print(redact(tab.text())[:1500])
        raise SystemExit("transfer did not reach the completion step")
    print("--- completed ---")
    print(redact(tab.text())[:1200])


def command_get(args) -> None:
    print(json.dumps(attach().fetch_json(args.path), ensure_ascii=False, indent=1))


def command_tx(args) -> None:
    """Current-account transactions. The API caps each call, so page by quarter."""
    tab = attach()
    path = ("/ServerServices/current-account/transactions"
            f"?numItemsPerPage=500&sortCode=1&retrievalStartDate={args.start}"
            f"&retrievalEndDate={args.end}&accountId={args.account}&lang=he")
    payload = tab.fetch_json(path)
    transactions = payload.get("transactions", [])
    if args.grep:
        transactions = [t for t in transactions
                        if args.grep in json.dumps(t, ensure_ascii=False)]
    print(json.dumps(transactions, ensure_ascii=False, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="log in with the Bitwarden credentials").set_defaults(func=command_login)
    sub.add_parser("accounts", help="list accounts and their API accountIds").set_defaults(func=command_accounts)

    switch = sub.add_parser("switch", help="switch the portal to a named account")
    switch.add_argument("name", help="substring of the account label, e.g. משפחה")
    switch.set_defaults(func=command_switch)

    get = sub.add_parser("get", help="GET any ServerServices path as JSON")
    get.add_argument("path")
    get.set_defaults(func=command_get)

    transactions = sub.add_parser("tx", help="current-account transactions for a date range")
    transactions.add_argument("account", help="accountId, e.g. 12-681-643943")
    transactions.add_argument("start", help="YYYYMMDD")
    transactions.add_argument("end", help="YYYYMMDD")
    transactions.add_argument("--grep", help="keep only records containing this string")
    transactions.set_defaults(func=command_tx)

    transfer = sub.add_parser("transfer", help="fill a transfer and stop on the confirmation step")
    transfer.add_argument("--from", dest="source", choices=sorted(SOURCE_ACCOUNTS), required=True,
                          help="source account: self = שלי פרטי, family = משפחה משותף")
    transfer.add_argument("--to", required=True, help="beneficiary name, e.g. רינת")
    transfer.add_argument("--amount", required=True, help="amount in NIS")
    transfer.add_argument("--comment", help=f"optional reason, max {COMMENT_MAX_CHARS} characters")
    transfer.set_defaults(func=command_transfer)

    sub.add_parser("send", help="click the final transfer button (explicit approval only)").set_defaults(func=command_send)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
