"""Data models used by the assurance runner and report renderers."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional

from ._version import VERSION


PASS = "pass"
FAIL = "fail"
ERROR = "error"


def utc_now() -> str:
    """Return a stable, RFC 3339 UTC timestamp representation."""

    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class Outcome:
    """The semantic outcome returned by one assurance check."""

    passed: bool
    message: str
    evidence: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls, message: str, evidence: Optional[Mapping[str, Any]] = None) -> "Outcome":
        return cls(True, message, evidence or {})

    @classmethod
    def failure(cls, message: str, evidence: Optional[Mapping[str, Any]] = None) -> "Outcome":
        return cls(False, message, evidence or {})


CheckFunction = Callable[[Any], Outcome]


@dataclass(frozen=True)
class Check:
    """A black-box assertion in an assurance profile."""

    id: str
    title: str
    requirement: str
    run: CheckFunction = field(repr=False, compare=False)

    def to_dict(self) -> Dict[str, str]:
        return {"id": self.id, "title": self.title, "requirement": self.requirement}


@dataclass(frozen=True)
class Profile:
    """An ordered collection of black-box assurance checks."""

    id: str
    title: str
    description: str
    checks: List[Check]

    def to_dict(self, include_checks: bool = True) -> Dict[str, Any]:
        value: Dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "check_count": len(self.checks),
        }
        if include_checks:
            value["checks"] = [check.to_dict() for check in self.checks]
        return value


@dataclass(frozen=True)
class CheckResult:
    """Serializable result of running one check."""

    id: str
    title: str
    requirement: str
    status: str
    message: str
    evidence: Mapping[str, Any]
    duration_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "requirement": self.requirement,
            "status": self.status,
            "message": self.message,
            "evidence": dict(self.evidence),
            "duration_ms": round(self.duration_ms, 3),
        }


@dataclass(frozen=True)
class RunResult:
    """Complete result of executing one profile against one provider."""

    profile: Profile
    provider_name: str
    started_at: str
    finished_at: str
    checks: List[CheckResult]

    @property
    def passed(self) -> int:
        return sum(1 for check in self.checks if check.status == PASS)

    @property
    def failed(self) -> int:
        return sum(1 for check in self.checks if check.status == FAIL)

    @property
    def errors(self) -> int:
        return sum(1 for check in self.checks if check.status == ERROR)

    @property
    def successful(self) -> bool:
        return self.failed == 0 and self.errors == 0

    def summary(self) -> Dict[str, Any]:
        return {
            "total": len(self.checks),
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "successful": self.successful,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": {"name": "legal-mcp-assurance", "version": VERSION},
            "profile": self.profile.to_dict(include_checks=False),
            "provider": self.provider_name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "summary": self.summary(),
            "checks": [check.to_dict() for check in self.checks],
        }
