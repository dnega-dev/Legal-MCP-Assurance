import unittest

from legal_mcp_assurance.example_data import broken_transcript, good_transcript
from legal_mcp_assurance.models import ERROR, FAIL, PASS
from legal_mcp_assurance.profiles import get_profile, list_profiles
from legal_mcp_assurance.provider import TranscriptProvider
from legal_mcp_assurance.runner import AssuranceRunner


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = get_profile("core")
        self.runner = AssuranceRunner()

    def test_core_profile_has_eighteen_stable_checks(self):
        self.assertEqual(18, len(self.profile.checks))
        self.assertEqual(
            ["LMA-{:03d}".format(index) for index in range(1, 19)],
            [check.id for check in self.profile.checks],
        )

    def test_profile_list_contains_core(self):
        self.assertEqual(["core"], [profile.id for profile in list_profiles()])

    def test_unknown_profile_raises_key_error(self):
        with self.assertRaises(KeyError):
            get_profile("missing")

    def test_good_transcript_passes_every_check(self):
        result = self.runner.run(self.profile, TranscriptProvider(good_transcript()))
        self.assertTrue(result.successful)
        self.assertEqual(18, result.passed)
        self.assertEqual(0, result.failed)
        self.assertEqual(0, result.errors)
        self.assertTrue(all(check.status == PASS for check in result.checks))

    def test_good_transcript_summary_is_consistent(self):
        result = self.runner.run(self.profile, TranscriptProvider(good_transcript()))
        self.assertEqual(
            {"total": 18, "passed": 18, "failed": 0, "errors": 0, "successful": True},
            result.summary(),
        )

    def test_broken_transcript_fails_every_check_without_crashing(self):
        result = self.runner.run(self.profile, TranscriptProvider(broken_transcript()))
        self.assertFalse(result.successful)
        self.assertEqual(0, result.passed)
        self.assertEqual(18, result.failed)
        self.assertEqual(0, result.errors)
        self.assertTrue(all(check.status == FAIL for check in result.checks))

    def test_broken_transcript_exercises_every_required_area(self):
        result = self.runner.run(self.profile, TranscriptProvider(broken_transcript()))
        failures = {check.id: check.message for check in result.checks}
        self.assertIn("read_only", failures["LMA-001"])
        self.assertIn("dry-run mutation", failures["LMA-002"])
        self.assertIn("round-trip", failures["LMA-003"])
        self.assertIn("unstable", failures["LMA-004"])
        self.assertIn("normalized", failures["LMA-005"])
        self.assertIn("jurisdiction", failures["LMA-006"])
        self.assertIn("retrieved_at", failures["LMA-007"])
        self.assertIn("as-of response", failures["LMA-008"])
        self.assertIn("cutoff", failures["LMA-009"])
        self.assertIn("source_hash", failures["LMA-010"])
        self.assertIn("source_hash", failures["LMA-011"])
        self.assertIn("coverage", failures["LMA-012"])
        self.assertIn("snapshot_at", failures["LMA-013"])
        self.assertIn("absent", failures["LMA-014"])
        self.assertIn("source_text", failures["LMA-015"])
        self.assertIn("recognized kind", failures["LMA-016"])
        self.assertIn("different response schemas", failures["LMA-017"])
        self.assertIn("different errors", failures["LMA-018"])

    def test_result_order_matches_profile_order(self):
        result = self.runner.run(self.profile, TranscriptProvider(good_transcript()))
        self.assertEqual([check.id for check in self.profile.checks], [check.id for check in result.checks])

    def test_runner_records_provider_exceptions_as_errors(self):
        class ExplodingProvider:
            name = "exploding"

            def call(self, operation, arguments):
                raise RuntimeError("offline")

        result = self.runner.run(self.profile, ExplodingProvider())
        self.assertEqual(18, result.errors)
        self.assertTrue(all(check.status == ERROR for check in result.checks))
        self.assertEqual("RuntimeError", result.checks[0].evidence["exception_type"])

    def test_adapter_without_reset_is_supported(self):
        delegate = TranscriptProvider(good_transcript())

        class NoResetAdapter:
            name = "no-reset"

            def call(self, operation, arguments):
                return delegate.call(operation, arguments)

        result = self.runner.run(self.profile, NoResetAdapter())
        self.assertTrue(result.successful)


if __name__ == "__main__":
    unittest.main()
