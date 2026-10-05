#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch
from urllib import request
import json

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import deepseek_prompt


class PromptFileTest(TestCase):
    def test_prompt_file_returns_answer_using_the_requested_model_and_provider(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            prompt_path = directory / "prompt.txt"
            prompt_path.write_text("Compare these two real passages: שלום", encoding="utf-8")
            (directory / ".openrouter-api-key").write_text("test-key\n")
            response = BytesIO(json.dumps({"choices": [{"message": {"content": "Only the old assumption is unique.", "reasoning_details": [{"type": "reasoning.text", "text": "private reasoning"}]}}]}).encode())
            with patch.object(Path, "home", return_value=directory), patch.object(request, "urlopen", return_value=response) as transport:
                answer = deepseek_prompt.complete(prompt_path)
            self.assertEqual(answer, "Only the old assumption is unique.", "The public interface must return only the assistant's text, not its reasoning or a wrapper.")
            sent_request = transport.call_args.args[0]
            sent_body = json.loads(sent_request.data)
            self.assertEqual(sent_request.full_url, "https://openrouter.ai/api/v1/chat/completions")
            self.assertEqual(sent_request.get_header("Authorization"), "Bearer test-key")
            self.assertEqual(sent_body, {"model": "deepseek/deepseek-v4.1-flash", "messages": [{"role": "user", "content": prompt_path.read_text()}], "reasoning": {"enabled": True}, "provider": {"only": ["together"], "allow_fallbacks": False}}, "The caller must not silently change the model, reasoning setting, provider or input text.")


if __name__ == "__main__":
    main()
