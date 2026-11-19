import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SESSION = "00000000-0000-4000-8000-000000000001"
PANE = "w1:p1"

# Fake only the Herdr CLI boundary. The wrappers still resolve, deliver and verify.
HERDR = r'''
import json
import os
from pathlib import Path
import sys

root = Path(os.environ["FIXTURE"])
case = json.loads((root / "case.json").read_text())
transcript = next(root.glob("*.jsonl"))
sent = root / "sent"
args = sys.argv[1:]
agent = {
    "pane_id": "w1:p1", "agent": "pi", "agent_status": case.get("status", "done"),
    "agent_session": {"kind": "path", "value": str(transcript)}, "state_change_seq": 23,
}
if args[:2] == ["agent", "list"]:
    print(json.dumps({"result": {"agents": [agent]}}))
elif args[:2] == ["agent", "get"]:
    print(json.dumps({"result": {"agent": agent}}))
elif args[:2] == ["agent", "wait"]:
    case["status"] = "done"
    (root / "case.json").write_text(json.dumps(case))
    print(json.dumps({"result": {"agent": agent}}))
elif args[:2] == ["pane", "process-info"]:
    print(json.dumps({"result": {"process_info": {"foreground_processes": [
        {"pid": 123, "argv0": "pi"}, *case.get("extra_processes", [])
    ]}}}))
elif args[:2] == ["agent", "read"]:
    completion = case.get("after", "") if sent.exists() else case.get("before", "")
    picker = completion if "Enter to select" in completion else case.get("draft", "")
    status = "" if picker == completion else completion
    print("Done\n" + status + "\n────────────────────────────────────────\n" + picker + "\n────────────────────────────────────────\n project/ ▃30%")
elif args[:2] == ["agent", "prompt"]:
    values = [arg for arg in args[2:] if arg != "--"]
    assert values[0] == "w1:p1", values
    sent.write_text(values[1])
    if case.get("receipt"):
        with transcript.open("a") as file:
            for row in case["receipt"]:
                file.write(json.dumps(row, separators=(",", ":")) + "\n")
    print(json.dumps({"result": {"type": "agent_prompted", "agent": agent}}))
else:
    sys.exit("Unexpected Herdr call: " + repr(args))
'''


class SessionCommands(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        fake = self.directory / "herdr"
        fake.write_text(f"#!{sys.executable}\n" + HERDR)
        fake.chmod(0o755)
        self.transcript = self.directory / f"2026-11-19T00-00-00-000Z_{SESSION}.jsonl"
        self.transcript.write_text(
            '{"type":"model_change","provider":"openai-codex","modelId":"gpt-6.1-sol"}\n'
            '{"type":"thinking_level_change","thinkingLevel":"xhigh"}\n'
        )

    def invoke(self, wrapper: str, *arguments: str, **case: object) -> subprocess.CompletedProcess[str]:
        (self.directory / "case.json").write_text(json.dumps(case))
        result = subprocess.run(
            [str(SCRIPTS / f"{wrapper}.sh"), *arguments],
            check=False, capture_output=True, text=True, timeout=12,
            env={**os.environ, "PATH": f"{self.directory}:{os.environ['PATH']}",
                 "FIXTURE": str(self.directory), "HERDR_ENV": "1", "PI_SESSION_ID": "00000000-0000-4000-8000-000000000002"},
        )
        self.assertEqual(result.stdout, "", result)
        return result

    def test_target_is_required(self) -> None:
        result = self.invoke("reload-session")
        self.assertEqual(result.returncode, 1, result)
        self.assertIn("target", result.stderr)
        self.assertFalse((self.directory / "sent").exists())

    def test_pane_model_switch_reports_both_native_values(self) -> None:
        result = self.invoke(
            "set-model", PANE, "--model", "openai-codex/gpt-6.2-sol",
            after="Model: gpt-6.2-sol",
            receipt=[{"type": "model_change", "provider": "openai-codex", "modelId": "gpt-6.2-sol"},
                     {"type": "thinking_level_change", "thinkingLevel": "high"}],
        )
        self.assertEqual(result.returncode, 0, result)
        self.assertIn("model=openai-codex/gpt-6.2-sol", result.stderr)
        self.assertIn("thinking=high", result.stderr)
        self.assertEqual((self.directory / "sent").read_text(), "/model openai-codex/gpt-6.2-sol")

    def test_no_wait_refuses_busy_without_sending(self) -> None:
        result = self.invoke("reload-session", PANE, "--no-wait-for-idle", status="working")
        self.assertEqual(result.returncode, 1, result)
        self.assertIn("state=working", result.stderr)
        self.assertIn("model=openai-codex/gpt-6.1-sol thinking=xhigh", result.stderr)
        self.assertFalse((self.directory / "sent").exists())

    def test_default_wait_settles_before_verified_reload(self) -> None:
        result = self.invoke(
            "reload-session", SESSION, status="working",
            after="Reloaded keybindings, extensions, skills, prompts, themes, and context files",
        )
        self.assertEqual(result.returncode, 0, result)
        self.assertEqual((self.directory / "sent").read_text(), "/reload")
        self.assertIn("reload verified", result.stderr)

    def test_draft_is_neither_cleared_nor_submitted(self) -> None:
        result = self.invoke("send-session-command", PANE, "--prompt", "/reload", draft="unsent text")
        self.assertEqual(result.returncode, 1, result)
        self.assertIn("empty Pi editor", result.stderr)
        self.assertNotIn("unsent text", result.stderr)
        self.assertFalse((self.directory / "sent").exists())

    def test_model_picker_miss_reports_actual_settings(self) -> None:
        result = self.invoke(
            "set-model", PANE, "--model", "openai-codex/gpt-6.2-sol",
            after="Scope: all | scoped\n> openai-codex/gpt-6.2-sol\n→ gpt-6.1-sol [openai-codex]\nEnter to select · Escape/Ctrl+C to cancel",
        )
        self.assertEqual(result.returncode, 1, result)
        self.assertIn("no selection made", result.stderr)
        self.assertIn("requested=model=openai-codex/gpt-6.2-sol", result.stderr)
        self.assertIn("observed model=openai-codex/gpt-6.1-sol thinking=xhigh", result.stderr)

    def test_thinking_refuses_wrong_effective_level(self) -> None:
        result = self.invoke(
            "set-thinking", PANE, "--level", "max", "--timeout", "1",
            after="Thinking level: high",
            receipt=[{"type": "thinking_level_change", "thinkingLevel": "high"}],
        )
        self.assertEqual(result.returncode, 1, result)
        self.assertIn("requested=thinking=max", result.stderr)
        self.assertIn("thinking=high", result.stderr)
        self.assertIn("not retried", result.stderr)

    def test_stale_reload_status_does_not_count(self) -> None:
        marker = "Reloaded keybindings, extensions, skills, prompts, themes, and context files"
        result = self.invoke("reload-session", PANE, "--timeout", "0.8", before=marker, after=marker)
        self.assertEqual(result.returncode, 1, result)
        self.assertIn("timeout", result.stderr)

    def test_multiple_foreground_processes_are_refused(self) -> None:
        result = self.invoke("reload-session", PANE, extra_processes=[{"pid": 456, "argv0": "pi"}])
        self.assertEqual(result.returncode, 1, result)
        self.assertIn("unique foreground", result.stderr)
        self.assertFalse((self.directory / "sent").exists())

    def test_generic_sender_does_not_claim_application(self) -> None:
        result = self.invoke("send-session-command", PANE, "--prompt", "/thinking high")
        self.assertEqual(result.returncode, 0, result)
        self.assertIn("delivered", result.stderr)
        self.assertIn("application not checked", result.stderr)
        self.assertEqual((self.directory / "sent").read_text(), "/thinking high")


if __name__ == "__main__":
    unittest.main()
