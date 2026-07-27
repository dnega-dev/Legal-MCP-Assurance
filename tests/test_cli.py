import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from legal_mcp_assurance.cli import main


ROOT = Path(__file__).resolve().parents[1]
GOOD = ROOT / "examples" / "good-transcript.json"
BROKEN = ROOT / "examples" / "broken-transcript.json"


class CliTests(unittest.TestCase):
    def invoke(self, arguments):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_profiles_list(self):
        code, stdout, stderr = self.invoke(["profiles", "list"])
        self.assertEqual(0, code)
        self.assertIn("core", stdout)
        self.assertIn("18 checks", stdout)
        self.assertEqual("", stderr)

    def test_profiles_show_json(self):
        code, stdout, stderr = self.invoke(["profiles", "show", "core", "--format", "json"])
        payload = json.loads(stdout)
        self.assertEqual(0, code)
        self.assertEqual("core", payload["id"])
        self.assertEqual(18, len(payload["checks"]))
        self.assertEqual("", stderr)

    def test_unknown_profile_returns_usage_error_code(self):
        code, stdout, stderr = self.invoke(["profiles", "show", "nope"])
        self.assertEqual(2, code)
        self.assertEqual("", stdout)
        self.assertIn("unknown profile", stderr)

    def test_good_run_returns_zero_and_json(self):
        code, stdout, stderr = self.invoke(
            ["run", "--transcript", str(GOOD), "--profile", "core", "--format", "json"]
        )
        self.assertEqual(0, code)
        self.assertTrue(json.loads(stdout)["summary"]["successful"])
        self.assertEqual("", stderr)

    def test_broken_run_returns_one(self):
        code, stdout, stderr = self.invoke(["run", "--transcript", str(BROKEN)])
        self.assertEqual(1, code)
        self.assertIn("18 failed", stdout)
        self.assertEqual("", stderr)

    def test_every_report_format_is_available(self):
        markers = {
            "text": "Legal MCP Assurance",
            "json": '"checks"',
            "junit": "<testsuite",
            "sarif": '"version": "2.1.0"',
        }
        for report_format, marker in markers.items():
            with self.subTest(report_format=report_format):
                code, stdout, stderr = self.invoke(
                    ["run", "--transcript", str(GOOD), "--format", report_format]
                )
                self.assertEqual(0, code)
                self.assertIn(marker, stdout)
                self.assertEqual("", stderr)

    def test_output_file_receives_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            destination = Path(directory) / "result.json"
            code, stdout, stderr = self.invoke(
                [
                    "run",
                    "--transcript",
                    str(GOOD),
                    "--format",
                    "json",
                    "--output",
                    str(destination),
                ]
            )
            self.assertEqual(0, code)
            self.assertEqual("", stdout)
            self.assertEqual("", stderr)
            self.assertTrue(json.loads(destination.read_text(encoding="utf-8"))["summary"]["successful"])

    def test_malformed_transcript_returns_two(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "bad.json"
            path.write_text("[]", encoding="utf-8")
            code, stdout, stderr = self.invoke(["run", "--transcript", str(path)])
            self.assertEqual(2, code)
            self.assertEqual("", stdout)
            self.assertIn("transcript root must be an object", stderr)

    def test_init_example_writes_file_and_does_not_overwrite_by_default(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "example.json"
            first = self.invoke(["init", "example", str(path)])
            second = self.invoke(["init", "example", str(path)])
            self.assertEqual(0, first[0])
            self.assertTrue(path.exists())
            self.assertEqual("1.0", json.loads(path.read_text(encoding="utf-8"))["transcript_version"])
            self.assertEqual(2, second[0])
            self.assertIn("refusing to overwrite", second[2])

    def test_init_broken_example_sets_provider_name(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "broken.json"
            code, _, stderr = self.invoke(["init", "example", str(path), "--broken"])
            self.assertEqual(0, code)
            self.assertEqual("", stderr)
            self.assertEqual("example-broken-provider", json.loads(path.read_text(encoding="utf-8"))["name"])


if __name__ == "__main__":
    unittest.main()
