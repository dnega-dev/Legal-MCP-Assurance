import json
import unittest
import xml.etree.ElementTree as ET

from legal_mcp_assurance.example_data import broken_transcript, good_transcript
from legal_mcp_assurance.profiles import get_profile
from legal_mcp_assurance.provider import TranscriptProvider
from legal_mcp_assurance.reports import render_report
from legal_mcp_assurance.runner import AssuranceRunner


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile = get_profile("core")
        runner = AssuranceRunner()
        cls.good = runner.run(profile, TranscriptProvider(good_transcript()))
        cls.broken = runner.run(profile, TranscriptProvider(broken_transcript()))

    def test_text_report_contains_checks_and_summary(self):
        report = render_report(self.good, "text")
        self.assertIn("[PASS ] LMA-001", report)
        self.assertIn("18 passed, 0 failed, 0 errors, 18 total", report)
        self.assertTrue(report.endswith("Result: PASS\n"))

    def test_json_report_is_parseable_and_complete(self):
        report = json.loads(render_report(self.good, "json"))
        self.assertEqual("legal-mcp-assurance", report["tool"]["name"])
        self.assertEqual("core", report["profile"]["id"])
        self.assertEqual(18, report["summary"]["total"])
        self.assertEqual(18, len(report["checks"]))
        self.assertTrue(report["summary"]["successful"])

    def test_junit_report_is_parseable(self):
        suite = ET.fromstring(render_report(self.good, "junit"))
        self.assertEqual("testsuite", suite.tag)
        self.assertEqual("18", suite.attrib["tests"])
        self.assertEqual("0", suite.attrib["failures"])
        self.assertEqual(18, len(suite.findall("testcase")))

    def test_junit_report_marks_assurance_failures(self):
        suite = ET.fromstring(render_report(self.broken, "junit"))
        self.assertEqual("18", suite.attrib["failures"])
        self.assertEqual("0", suite.attrib["errors"])
        self.assertEqual(18, len(suite.findall("testcase/failure")))

    def test_sarif_success_has_rules_and_no_findings(self):
        report = json.loads(render_report(self.good, "sarif"))
        self.assertEqual("2.1.0", report["version"])
        run = report["runs"][0]
        self.assertEqual(18, len(run["tool"]["driver"]["rules"]))
        self.assertEqual([], run["results"])
        self.assertTrue(run["invocations"][0]["executionSuccessful"])

    def test_sarif_failure_has_one_finding_per_failed_check(self):
        report = json.loads(render_report(self.broken, "sarif"))
        findings = report["runs"][0]["results"]
        self.assertEqual(18, len(findings))
        self.assertEqual("LMA-001", findings[0]["ruleId"])
        self.assertEqual("fail", findings[0]["properties"]["status"])

    def test_unknown_report_format_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown report format"):
            render_report(self.good, "yaml")


if __name__ == "__main__":
    unittest.main()
