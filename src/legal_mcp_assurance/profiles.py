"""Built-in black-box assurance profiles and their canonical probes."""

import hashlib
import json
import re
from datetime import date, datetime
from typing import Any, List, Mapping, Optional, Tuple

from .models import Check, Outcome, Profile


DOCUMENT_ID = "doc-roe-410-us-113"
DOCUMENT_REQUEST = {"document_id": DOCUMENT_ID}
SEARCH_REQUEST = {"query": "410 U.S. 113", "limit": 1}
AS_OF_REQUEST = {"query": "example authority", "as_of": "2000-01-01", "limit": 10}
MISSING_REQUEST = {"query": "Imaginary Reporter 999 X.Y. 999", "limit": 5}
INTERPRETATION_REQUEST = {"document_id": DOCUMENT_ID, "question": "What is the holding?"}
INVALID_REQUEST = {"query": 17, "limit": -1}
READ_ONLY_PROBE_REQUEST = {"operation": "create_annotation", "mode": "dry-run"}

_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_CITATION = re.compile(r"^[1-9][0-9]* [A-Za-z][A-Za-z.0-9]* [1-9][0-9]*$")


def _call(provider: Any, operation: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    response = provider.call(operation, arguments)
    if not isinstance(response, Mapping):
        raise TypeError("provider response for {} must be an object".format(operation))
    return response


def _fail(message: str, **evidence: Any) -> Outcome:
    return Outcome.failure(message, evidence)


def _iso_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _iso_date(value: Any) -> Optional[date]:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _first_result(response: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    results = response.get("results")
    if not isinstance(results, list) or not results or not isinstance(results[0], Mapping):
        return None
    return results[0]


def _document_content(provider: Any) -> Tuple[Optional[str], Optional[Mapping[str, Any]], Optional[Outcome]]:
    document = _call(provider, "document.get", DOCUMENT_REQUEST)
    if document.get("state") != "found":
        return None, None, _fail("document.get did not return state=found", state=document.get("state"))
    if document.get("document_id") != DOCUMENT_ID:
        return None, None, _fail(
            "document.get did not preserve the requested document_id",
            expected=DOCUMENT_ID,
            actual=document.get("document_id"),
        )
    content = document.get("content")
    if not isinstance(content, str) or not content:
        return None, None, _fail("document content must be a non-empty string")
    return content, document, None


def check_read_only_declaration(provider: Any) -> Outcome:
    capabilities = _call(provider, "capabilities.get", {})
    if capabilities.get("read_only") is not True:
        return _fail("provider did not declare read_only=true", read_only=capabilities.get("read_only"))
    mutating = capabilities.get("mutating_operations")
    if mutating != []:
        return _fail("read-only declaration must expose an empty mutating_operations array", actual=mutating)
    return Outcome.success("provider declares read-only behavior and no mutating operations")


def check_read_only_probe(provider: Any) -> Outcome:
    probe = _call(provider, "capabilities.read_only_probe", READ_ONLY_PROBE_REQUEST)
    expected = {"state": "rejected", "code": "READ_ONLY", "side_effects": False}
    actual = {key: probe.get(key) for key in expected}
    if actual != expected:
        return _fail("dry-run mutation probe was not explicitly rejected without side effects", expected=expected, actual=actual)
    return Outcome.success("dry-run mutation probe was rejected without declared side effects")


def check_quote_span(provider: Any) -> Outcome:
    content, _, failure = _document_content(provider)
    if failure:
        return failure
    quote = _call(provider, "quote.get", {"document_id": DOCUMENT_ID, "selector": "holding"})
    span = quote.get("span")
    if quote.get("document_id") != DOCUMENT_ID or not isinstance(span, Mapping):
        return _fail("quote response must identify the document and provide a span")
    start, end = span.get("start"), span.get("end")
    if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool):
        return _fail("quote span offsets must be integers", span=span)
    if start < 0 or end <= start or end > len(content or ""):
        return _fail("quote span is outside document bounds", span=span, content_length=len(content or ""))
    exact = (content or "")[start:end]
    if quote.get("quote") != exact:
        return _fail("quote text does not exactly round-trip through its source span", expected=exact, actual=quote.get("quote"))
    return Outcome.success("quote exactly matches document content at the declared span", {"span": {"start": start, "end": end}})


def check_stable_document_ids(provider: Any) -> Outcome:
    first = _first_result(_call(provider, "search", SEARCH_REQUEST))
    second = _first_result(_call(provider, "search", SEARCH_REQUEST))
    if first is None or second is None:
        return _fail("repeated searches must each return at least one result")
    first_id, second_id = first.get("document_id"), second.get("document_id")
    if not isinstance(first_id, str) or not first_id:
        return _fail("search result document_id must be a non-empty string", actual=first_id)
    if first_id != second_id:
        return _fail("identical searches returned unstable document IDs", first=first_id, second=second_id)
    return Outcome.success("identical searches returned a stable document ID", {"document_id": first_id})


def check_citation_normalization(provider: Any) -> Outcome:
    result = _first_result(_call(provider, "search", SEARCH_REQUEST))
    citation = result.get("citation") if result else None
    if not isinstance(citation, Mapping):
        return _fail("search result must include a citation object")
    canonical = citation.get("canonical")
    if canonical != "410 U.S. 113" or not _CITATION.fullmatch(str(canonical)):
        return _fail("citation was not normalized to the expected canonical reporter form", actual=canonical)
    if not isinstance(citation.get("display"), str) or not citation.get("display"):
        return _fail("citation must retain a non-empty display form")
    if citation.get("normalization") != "reporter-volume-page":
        return _fail("citation normalization method must be explicit", actual=citation.get("normalization"))
    return Outcome.success("citation includes canonical, display, and normalization forms", {"canonical": canonical})


def check_jurisdiction_metadata(provider: Any) -> Outcome:
    result = _first_result(_call(provider, "search", SEARCH_REQUEST))
    jurisdiction = result.get("jurisdiction") if result else None
    if not isinstance(jurisdiction, Mapping):
        return _fail("search result must contain structured jurisdiction metadata")
    if not all(isinstance(jurisdiction.get(key), str) and jurisdiction.get(key) for key in ("code", "name")):
        return _fail("jurisdiction requires non-empty code and name", jurisdiction=jurisdiction)
    return Outcome.success("structured jurisdiction metadata is present", {"jurisdiction": dict(jurisdiction)})


def check_retrieval_timestamp(provider: Any) -> Outcome:
    response = _call(provider, "search", SEARCH_REQUEST)
    timestamp = response.get("retrieved_at")
    parsed = _iso_datetime(timestamp)
    if parsed is None:
        return _fail("search response retrieved_at must be a timezone-aware ISO 8601 timestamp", actual=timestamp)
    return Outcome.success("retrieval timestamp is explicit and timezone-aware", {"retrieved_at": timestamp})


def _as_of_response(provider: Any) -> Tuple[Mapping[str, Any], str]:
    return _call(provider, "search.as_of", AS_OF_REQUEST), AS_OF_REQUEST["as_of"]


def check_as_of_contract(provider: Any) -> Outcome:
    response, requested = _as_of_response(provider)
    if response.get("as_of") != requested or response.get("state") not in ("found", "absent"):
        return _fail("as-of response must echo the requested date and expose found/absent state", response_as_of=response.get("as_of"), state=response.get("state"))
    if _iso_datetime(response.get("retrieved_at")) is None:
        return _fail("as-of response requires a timezone-aware retrieval timestamp")
    if not isinstance(response.get("results"), list):
        return _fail("as-of response results must be an array")
    return Outcome.success("as-of response echoes its cutoff with explicit state and retrieval time", {"as_of": requested})


def check_as_of_effective_intervals(provider: Any) -> Outcome:
    response, requested = _as_of_response(provider)
    cutoff = _iso_date(requested)
    results = response.get("results")
    if not isinstance(results, list):
        return _fail("as-of response results must be an array")
    for index, result in enumerate(results):
        if not isinstance(result, Mapping):
            return _fail("as-of result must be an object", index=index)
        effective = _iso_date(result.get("effective_from"))
        if effective is None or (cutoff is not None and effective > cutoff):
            return _fail("as-of search leaked an authority effective after the cutoff", index=index, effective_from=result.get("effective_from"), cutoff=requested)
        effective_to = result.get("effective_to")
        if effective_to is not None:
            end = _iso_date(effective_to)
            if end is None or (cutoff is not None and end < cutoff):
                return _fail("as-of result was no longer effective at the cutoff", index=index, effective_to=effective_to, cutoff=requested)
    return Outcome.success("all as-of results are effective at the requested cutoff", {"as_of": requested, "result_count": len(results)})


def check_source_hash_declaration(provider: Any) -> Outcome:
    _, document, failure = _document_content(provider)
    if failure:
        return failure
    source_hash = document.get("source_hash") if document else None
    if not isinstance(source_hash, str) or not _SHA256.fullmatch(source_hash):
        return _fail("source_hash must use lowercase sha256:<64 hex> form", actual=source_hash)
    return Outcome.success("source hash declares lowercase SHA-256 syntax", {"source_hash": source_hash})


def check_source_hash_integrity(provider: Any) -> Outcome:
    content, document, failure = _document_content(provider)
    if failure:
        return failure
    source_hash = document.get("source_hash") if document else None
    expected = "sha256:" + hashlib.sha256((content or "").encode("utf-8")).hexdigest()
    if not isinstance(source_hash, str) or not _SHA256.fullmatch(source_hash):
        return _fail("source_hash is not a valid SHA-256 declaration", actual=source_hash)
    if source_hash != expected:
        return _fail("source_hash does not match the returned source bytes", expected=expected, actual=source_hash)
    return Outcome.success("source hash matches the returned UTF-8 source text", {"source_hash": source_hash})


def check_coverage(provider: Any) -> Outcome:
    status = _call(provider, "corpus.status", {})
    coverage = status.get("coverage")
    if not isinstance(coverage, Mapping):
        return _fail("corpus status must expose a coverage object")
    required_arrays = ("jurisdictions", "authority_types", "exclusions")
    if any(not isinstance(coverage.get(key), list) for key in required_arrays):
        return _fail("coverage requires jurisdictions, authority_types, and exclusions arrays")
    if not coverage.get("jurisdictions") or not coverage.get("authority_types"):
        return _fail("coverage jurisdictions and authority_types must not be empty")
    dates = coverage.get("publication_date_range")
    if not isinstance(dates, Mapping):
        return _fail("coverage requires an explicit publication_date_range")
    range_start = _iso_date(dates.get("from"))
    range_end = _iso_date(dates.get("through"))
    if range_start is None or range_end is None or range_start > range_end:
        return _fail("coverage publication_date_range must be valid and ordered", date_range=dict(dates))
    return Outcome.success("corpus scope, date range, and exclusions are explicit", {"coverage": dict(coverage)})


def check_freshness(provider: Any) -> Outcome:
    status = _call(provider, "corpus.status", {})
    freshness = status.get("freshness")
    if not isinstance(freshness, Mapping):
        return _fail("corpus status must expose a freshness object")
    snapshot = freshness.get("snapshot_at")
    if _iso_datetime(snapshot) is None:
        return _fail("freshness.snapshot_at must be a timezone-aware ISO 8601 timestamp", actual=snapshot)
    max_age = freshness.get("max_age_days")
    if not isinstance(max_age, int) or isinstance(max_age, bool) or max_age < 0:
        return _fail("freshness.max_age_days must be a non-negative integer", actual=max_age)
    if freshness.get("status") not in ("current", "stale", "unknown"):
        return _fail("freshness.status must be current, stale, or unknown", actual=freshness.get("status"))
    if not isinstance(freshness.get("basis"), str) or not freshness.get("basis"):
        return _fail("freshness basis must be explicit")
    return Outcome.success("corpus snapshot and freshness policy are explicit", {"freshness": dict(freshness)})


def check_explicit_absence(provider: Any) -> Outcome:
    response = _call(provider, "search", MISSING_REQUEST)
    results = response.get("results")
    if response.get("state") != "absent" or results != []:
        return _fail("missing authority must return state=absent and an empty results array", state=response.get("state"), results=results)
    absence = response.get("absence")
    if not isinstance(absence, Mapping) or absence.get("code") != "NO_MATCH":
        return _fail("absence state requires a structured NO_MATCH reason", absence=absence)
    if response.get("query") != MISSING_REQUEST["query"]:
        return _fail("absence response must echo the attempted query", actual=response.get("query"))
    return Outcome.success("missing authority is represented by an explicit structured absence state")


def _interpretation_segments(provider: Any) -> Tuple[Optional[str], Any, Optional[Outcome]]:
    content, _, failure = _document_content(provider)
    if failure:
        return None, None, failure
    segments = _call(provider, "interpret", INTERPRETATION_REQUEST).get("segments")
    if not isinstance(segments, list) or not segments:
        return None, None, _fail("interpretation response must expose typed segments")
    return content, segments, None


def check_interpretation_source_fidelity(provider: Any) -> Outcome:
    content, segments, failure = _interpretation_segments(provider)
    if failure:
        return failure
    source_count = 0
    for index, segment in enumerate(segments):
        if not isinstance(segment, Mapping):
            return _fail("interpretation segment must be an object", index=index)
        if segment.get("kind") != "source_text":
            continue
        source_count += 1
        span = segment.get("span")
        if not isinstance(span, Mapping):
            return _fail("source_text segment requires a source span", index=index)
        start, end = span.get("start"), span.get("end")
        if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool):
            return _fail("source_text segment span requires integer offsets", index=index)
        if start < 0 or end <= start or end > len(content or "") or segment.get("text") != (content or "")[start:end]:
            return _fail("source_text segment does not round-trip to the document", index=index)
    if source_count == 0:
        return _fail("interpretation response must include at least one exact source_text segment")
    return Outcome.success("interpretation source segments round-trip to the document", {"source_segments": source_count})


def check_generated_interpretation_separation(provider: Any) -> Outcome:
    _, segments, failure = _interpretation_segments(provider)
    if failure:
        return failure
    generated_count = 0
    for index, segment in enumerate(segments):
        if not isinstance(segment, Mapping):
            return _fail("interpretation segment must be an object", index=index)
        kind = segment.get("kind")
        if kind not in ("source_text", "generated_interpretation"):
            return _fail("every interpretation segment must declare a recognized kind", index=index, kind=kind)
        if kind == "generated_interpretation":
            generated_count += 1
            if segment.get("label") != "Generated interpretation" or not isinstance(segment.get("text"), str) or not segment.get("text"):
                return _fail("generated interpretation must be non-empty and explicitly labeled", index=index)
    if generated_count == 0:
        return _fail("response must include explicitly labeled generated interpretation")
    return Outcome.success("generated interpretation is explicitly typed and labeled", {"generated_segments": generated_count})


def _schema(value: Any) -> Any:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Mapping):
        return {str(key): _schema(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, list):
        item_schemas = []
        for item in value:
            candidate = _schema(item)
            encoded = json.dumps(candidate, sort_keys=True, separators=(",", ":"))
            if all(json.dumps(existing, sort_keys=True, separators=(",", ":")) != encoded for existing in item_schemas):
                item_schemas.append(candidate)
        return {"array": item_schemas}
    return type(value).__name__


def check_deterministic_schema(provider: Any) -> Outcome:
    first = _call(provider, "search", SEARCH_REQUEST)
    second = _call(provider, "search", SEARCH_REQUEST)
    first_schema, second_schema = _schema(first), _schema(second)
    if first_schema != second_schema:
        return _fail("identical calls returned different response schemas", first_schema=first_schema, second_schema=second_schema)
    required = {"state", "query", "retrieved_at", "results"}
    missing = sorted(required.difference(first.keys()))
    if missing:
        return _fail("search response schema is missing required fields", missing=missing)
    return Outcome.success("identical calls returned the same response schema")


def check_deterministic_errors(provider: Any) -> Outcome:
    first = _call(provider, "search", INVALID_REQUEST)
    second = _call(provider, "search", INVALID_REQUEST)
    if first != second:
        return _fail("identical invalid requests returned different errors", first=dict(first), second=dict(second))
    if set(first.keys()) != {"state", "error"} or first.get("state") != "error":
        return _fail("invalid request must return the deterministic state/error envelope", keys=sorted(str(key) for key in first.keys()), state=first.get("state"))
    error = first.get("error")
    if not isinstance(error, Mapping) or set(error.keys()) != {"code", "message", "details"}:
        return _fail("error object must contain exactly code, message, and details")
    if not isinstance(error.get("code"), str) or not error.get("code") or not isinstance(error.get("message"), str) or not error.get("message") or not isinstance(error.get("details"), Mapping):
        return _fail("error code/message/details types are not deterministic")
    return Outcome.success("invalid requests return an exact deterministic error envelope", {"code": error.get("code")})


_CORE_CHECKS = [
    Check("LMA-001", "Read-only capability declaration", "Declare read_only=true and an empty mutating_operations array.", check_read_only_declaration),
    Check("LMA-002", "Read-only mutation rejection", "Reject a dry-run mutation probe with READ_ONLY and no declared side effects.", check_read_only_probe),
    Check("LMA-003", "Exact quote/source-span round trip", "Return quote text that exactly equals the declared document character span.", check_quote_span),
    Check("LMA-004", "Stable document identifiers", "Return the same non-empty document ID for identical retrievals.", check_stable_document_ids),
    Check("LMA-005", "Citation normalization", "Expose canonical and display citation forms with an explicit normalization method.", check_citation_normalization),
    Check("LMA-006", "Jurisdiction metadata", "Return structured jurisdiction code and name for retrieved authority.", check_jurisdiction_metadata),
    Check("LMA-007", "Retrieval timestamp", "Return a timezone-aware ISO 8601 retrieval timestamp.", check_retrieval_timestamp),
    Check("LMA-008", "As-of response contract", "Echo an as-of date with an explicit state, results array, and retrieval timestamp.", check_as_of_contract),
    Check("LMA-009", "Point-in-time effective intervals", "Exclude authority outside its effective interval at the requested as-of date.", check_as_of_effective_intervals),
    Check("LMA-010", "Source hash declaration", "Declare a lowercase sha256 source hash with exactly 64 hexadecimal digits.", check_source_hash_declaration),
    Check("LMA-011", "Source hash integrity", "Return a SHA-256 source hash matching the returned UTF-8 source text.", check_source_hash_integrity),
    Check("LMA-012", "Explicit corpus coverage", "Declare jurisdictions, authority types, publication date range, and exclusions.", check_coverage),
    Check("LMA-013", "Explicit corpus freshness", "Declare corpus snapshot, freshness status, policy, and basis.", check_freshness),
    Check("LMA-014", "Explicit absence state", "Represent a missing authority with a structured absence state instead of an empty success.", check_explicit_absence),
    Check("LMA-015", "Interpretation source fidelity", "Round-trip every source_text interpretation segment to its document span.", check_interpretation_source_fidelity),
    Check("LMA-016", "Generated interpretation separation", "Type and label generated interpretation distinctly from source text.", check_generated_interpretation_separation),
    Check("LMA-017", "Deterministic response schema", "Return the same response schema for identical valid requests.", check_deterministic_schema),
    Check("LMA-018", "Deterministic errors", "Return the same exact structured error for identical invalid requests.", check_deterministic_errors),
]

_CORE = Profile(
    id="core",
    title="Legal Retrieval Core Assurance",
    description=(
        "Black-box checks for provenance, temporal semantics, corpus transparency, "
        "absence handling, source separation, and deterministic contracts."
    ),
    checks=_CORE_CHECKS,
)

_PROFILES = {_CORE.id: _CORE}


def list_profiles() -> List[Profile]:
    """Return built-in profiles in deterministic ID order."""

    return [_PROFILES[key] for key in sorted(_PROFILES)]


def get_profile(profile_id: str) -> Profile:
    """Return a profile or raise KeyError for an unknown ID."""

    return _PROFILES[profile_id]
