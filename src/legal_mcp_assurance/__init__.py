"""Zero-dependency black-box assurance for legal/retrieval provider adapters."""

from ._version import VERSION as __version__
from .models import Check, CheckResult, Outcome, Profile, RunResult
from .profiles import get_profile, list_profiles
from .provider import ProviderAdapter, ProviderCallError, TranscriptFormatError, TranscriptProvider
from .runner import AssuranceRunner

__all__ = [
    "AssuranceRunner",
    "Check",
    "CheckResult",
    "Outcome",
    "Profile",
    "ProviderAdapter",
    "ProviderCallError",
    "RunResult",
    "TranscriptFormatError",
    "TranscriptProvider",
    "__version__",
    "get_profile",
    "list_profiles",
]
