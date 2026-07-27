"""Profile execution engine."""

import time
from typing import Any

from .models import ERROR, FAIL, PASS, CheckResult, Profile, RunResult, utc_now


class AssuranceRunner:
    """Execute profile checks against a provider adapter."""

    def run(self, profile: Profile, provider: Any) -> RunResult:
        started_at = utc_now()
        results = []
        for check in profile.checks:
            started = time.perf_counter()
            try:
                reset = getattr(provider, "reset", None)
                if callable(reset):
                    reset()
                outcome = check.run(provider)
                status = PASS if outcome.passed else FAIL
                message = outcome.message
                evidence = outcome.evidence
            except Exception as exc:  # A provider boundary must not abort the suite.
                status = ERROR
                message = "{}: {}".format(type(exc).__name__, exc)
                evidence = {"exception_type": type(exc).__name__}
            duration_ms = (time.perf_counter() - started) * 1000.0
            results.append(
                CheckResult(
                    id=check.id,
                    title=check.title,
                    requirement=check.requirement,
                    status=status,
                    message=message,
                    evidence=evidence,
                    duration_ms=duration_ms,
                )
            )
        name = getattr(provider, "name", type(provider).__name__)
        if not isinstance(name, str) or not name:
            name = type(provider).__name__
        return RunResult(
            profile=profile,
            provider_name=name,
            started_at=started_at,
            finished_at=utc_now(),
            checks=results,
        )
