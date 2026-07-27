"""Text, JSON, JUnit XML, and SARIF report renderers."""

import json
import xml.etree.ElementTree as ET
from typing import Callable, Dict

from ._version import VERSION
from .models import ERROR, FAIL, PASS, RunResult


REPORT_FORMATS = ("text", "json", "junit", "sarif")


def render_text(result: RunResult) -> str:
    lines = [
        "Legal MCP Assurance",
        "Profile: {} ({})".format(result.profile.title, result.profile.id),
        "Provider: {}".format(result.provider_name),
        "",
    ]
    for check in result.checks:
        lines.append("[{:<5}] {} {}".format(check.status.upper(), check.id, check.title))
        lines.append("        {}".format(check.message))
    summary = result.summary()
    lines.extend(
        [
            "",
            "Summary: {passed} passed, {failed} failed, {errors} errors, {total} total".format(**summary),
            "Result: {}".format("PASS" if result.successful else "FAIL"),
        ]
    )
    return "\n".join(lines) + "\n"


def render_json(result: RunResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_junit(result: RunResult) -> str:
    total_seconds = sum(check.duration_ms for check in result.checks) / 1000.0
    suite = ET.Element(
        "testsuite",
        {
            "name": "legal-mcp-assurance.{}".format(result.profile.id),
            "tests": str(len(result.checks)),
            "failures": str(result.failed),
            "errors": str(result.errors),
            "skipped": "0",
            "time": "{:.6f}".format(total_seconds),
            "timestamp": result.started_at,
        },
    )
    properties = ET.SubElement(suite, "properties")
    ET.SubElement(properties, "property", {"name": "provider", "value": result.provider_name})
    ET.SubElement(properties, "property", {"name": "profile", "value": result.profile.id})
    for check in result.checks:
        case = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": "legal_mcp_assurance.{}".format(result.profile.id),
                "name": "{} {}".format(check.id, check.title),
                "time": "{:.6f}".format(check.duration_ms / 1000.0),
            },
        )
        if check.status == FAIL:
            node = ET.SubElement(case, "failure", {"message": check.message, "type": "assurance_failure"})
            node.text = json.dumps(dict(check.evidence), sort_keys=True, ensure_ascii=False)
        elif check.status == ERROR:
            node = ET.SubElement(case, "error", {"message": check.message, "type": "provider_error"})
            node.text = json.dumps(dict(check.evidence), sort_keys=True, ensure_ascii=False)
        output = ET.SubElement(case, "system-out")
        output.text = json.dumps(
            {"status": check.status, "message": check.message, "evidence": dict(check.evidence)},
            sort_keys=True,
            ensure_ascii=False,
        )
    ET.indent(suite, space="  ")
    return ET.tostring(suite, encoding="unicode", xml_declaration=True) + "\n"


def render_sarif(result: RunResult) -> str:
    rules = []
    for check in result.profile.checks:
        rules.append(
            {
                "id": check.id,
                "name": check.title,
                "shortDescription": {"text": check.title},
                "fullDescription": {"text": check.requirement},
                "defaultConfiguration": {"level": "error"},
                "properties": {"profile": result.profile.id},
            }
        )
    findings = []
    for check in result.checks:
        if check.status == PASS:
            continue
        findings.append(
            {
                "ruleId": check.id,
                "level": "error",
                "kind": "fail",
                "message": {"text": check.message},
                "properties": {
                    "status": check.status,
                    "evidence": dict(check.evidence),
                    "duration_ms": round(check.duration_ms, 3),
                },
            }
        )
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "legal-mcp-assurance",
                        "version": VERSION,
                        "rules": rules,
                    }
                },
                "invocations": [
                    {
                        "executionSuccessful": result.errors == 0,
                        "startTimeUtc": result.started_at,
                        "endTimeUtc": result.finished_at,
                        "properties": {
                            "provider": result.provider_name,
                            "profile": result.profile.id,
                            "assuranceSuccessful": result.successful,
                        },
                    }
                ],
                "results": findings,
            }
        ],
    }
    return json.dumps(sarif, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


_RENDERERS: Dict[str, Callable[[RunResult], str]] = {
    "text": render_text,
    "json": render_json,
    "junit": render_junit,
    "sarif": render_sarif,
}


def render_report(result: RunResult, report_format: str) -> str:
    """Render a result in one of the supported formats."""

    try:
        renderer = _RENDERERS[report_format]
    except KeyError as exc:
        raise ValueError("unknown report format: {}".format(report_format)) from exc
    return renderer(result)
