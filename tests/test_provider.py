import json
import tempfile
import unittest
from pathlib import Path

from legal_mcp_assurance.example_data import good_transcript
from legal_mcp_assurance.provider import (
    ProviderAdapter,
    ProviderCallError,
    TranscriptFormatError,
    TranscriptProvider,
)


ROOT = Path(__file__).resolve().parents[1]


class TranscriptProviderTests(unittest.TestCase):
    def test_transcript_provider_satisfies_adapter_protocol(self):
        provider = TranscriptProvider(good_transcript())
        self.assertIsInstance(provider, ProviderAdapter)
        self.assertEqual("example-good-provider", provider.name)

    def test_duplicate_requests_replay_in_order_and_then_reuse_last(self):
        transcript = {
            "transcript_version": "1.0",
            "name": "sequence",
            "exchanges": [
                {"request": {"operation": "x", "arguments": {}}, "response": {"value": 1}},
                {"request": {"operation": "x", "arguments": {}}, "response": {"value": 2}},
            ],
        }
        provider = TranscriptProvider(transcript)
        self.assertEqual({"value": 1}, provider.call("x", {}))
        self.assertEqual({"value": 2}, provider.call("x", {}))
        self.assertEqual({"value": 2}, provider.call("x", {}))

    def test_reset_rewinds_duplicate_sequence(self):
        transcript = {
            "transcript_version": "1.0",
            "name": "sequence",
            "exchanges": [
                {"request": {"operation": "x", "arguments": {}}, "response": {"value": 1}},
                {"request": {"operation": "x", "arguments": {}}, "response": {"value": 2}},
            ],
        }
        provider = TranscriptProvider(transcript)
        provider.call("x", {})
        provider.reset()
        self.assertEqual({"value": 1}, provider.call("x", {}))

    def test_response_is_deep_copied(self):
        transcript = {
            "transcript_version": "1.0",
            "name": "copy",
            "exchanges": [
                {
                    "request": {"operation": "x", "arguments": {}},
                    "response": {"nested": {"items": [1]}},
                }
            ],
        }
        provider = TranscriptProvider(transcript)
        first = provider.call("x", {})
        first["nested"]["items"].append(2)
        self.assertEqual({"nested": {"items": [1]}}, provider.call("x", {}))

    def test_argument_key_order_does_not_affect_matching(self):
        transcript = {
            "transcript_version": "1.0",
            "name": "canonical",
            "exchanges": [
                {
                    "request": {"operation": "x", "arguments": {"a": 1, "b": 2}},
                    "response": {"ok": True},
                }
            ],
        }
        provider = TranscriptProvider(transcript)
        self.assertEqual({"ok": True}, provider.call("x", {"b": 2, "a": 1}))

    def test_transcript_miss_raises_structured_error(self):
        provider = TranscriptProvider(good_transcript())
        with self.assertRaises(ProviderCallError) as caught:
            provider.call("unknown", {})
        self.assertEqual("TRANSCRIPT_MISS", caught.exception.code)
        self.assertEqual("unknown", caught.exception.details["operation"])

    def test_error_exchange_raises_structured_error(self):
        transcript = {
            "transcript_version": "1.0",
            "name": "error",
            "exchanges": [
                {
                    "request": {"operation": "x", "arguments": {}},
                    "error": {"code": "OFFLINE", "message": "not available", "details": {"retry": False}},
                }
            ],
        }
        provider = TranscriptProvider(transcript)
        with self.assertRaises(ProviderCallError) as caught:
            provider.call("x", {})
        self.assertEqual(
            {"code": "OFFLINE", "message": "not available", "details": {"retry": False}},
            caught.exception.to_dict(),
        )

    def test_rejects_wrong_transcript_version(self):
        transcript = good_transcript()
        transcript["transcript_version"] = "2.0"
        with self.assertRaisesRegex(TranscriptFormatError, "transcript_version"):
            TranscriptProvider(transcript)

    def test_rejects_empty_exchange_array(self):
        with self.assertRaisesRegex(TranscriptFormatError, "non-empty"):
            TranscriptProvider({"transcript_version": "1.0", "name": "empty", "exchanges": []})

    def test_rejects_exchange_with_response_and_error(self):
        transcript = {
            "transcript_version": "1.0",
            "name": "ambiguous",
            "exchanges": [
                {
                    "request": {"operation": "x", "arguments": {}},
                    "response": {},
                    "error": {"code": "X", "message": "x"},
                }
            ],
        }
        with self.assertRaisesRegex(TranscriptFormatError, "exactly one"):
            TranscriptProvider(transcript)

    def test_from_file_rejects_malformed_json(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(TranscriptFormatError, "could not read"):
                TranscriptProvider.from_file(str(path))

    def test_from_file_loads_valid_transcript(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "good.json"
            path.write_text(json.dumps(good_transcript()), encoding="utf-8")
            provider = TranscriptProvider.from_file(str(path))
            self.assertEqual("example-good-provider", provider.name)


if __name__ == "__main__":
    unittest.main()
