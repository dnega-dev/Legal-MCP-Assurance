"""Self-contained example transcripts used by ``init example`` and tests."""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping

from .profiles import (
    AS_OF_REQUEST,
    DOCUMENT_ID,
    DOCUMENT_REQUEST,
    INTERPRETATION_REQUEST,
    INVALID_REQUEST,
    MISSING_REQUEST,
    READ_ONLY_PROBE_REQUEST,
    SEARCH_REQUEST,
)


CONTENT = "The Court held that the challenged restriction violated the Constitution."
SOURCE_QUOTE = "the challenged restriction violated the Constitution"
SOURCE_START = CONTENT.index(SOURCE_QUOTE)
SOURCE_END = SOURCE_START + len(SOURCE_QUOTE)
SOURCE_HASH = "sha256:" + hashlib.sha256(CONTENT.encode("utf-8")).hexdigest()


def _exchange(operation: str, arguments: Mapping[str, Any], response: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "request": {"operation": operation, "arguments": dict(arguments)},
        "response": dict(response),
    }


def _good_search(document_id: str = DOCUMENT_ID) -> Dict[str, Any]:
    return {
        "state": "found",
        "query": SEARCH_REQUEST["query"],
        "retrieved_at": "2025-01-15T12:00:00Z",
        "results": [
            {
                "document_id": document_id,
                "title": "Example reported decision",
                "citation": {
                    "canonical": "410 U.S. 113",
                    "display": "Example Decision, 410 U.S. 113 (1973)",
                    "normalization": "reporter-volume-page",
                },
                "jurisdiction": {
                    "code": "us-federal",
                    "name": "United States",
                    "court": "Supreme Court of the United States",
                },
                "effective_from": "1973-01-22",
                "effective_to": None,
                "source_hash": SOURCE_HASH,
            }
        ],
    }


def good_transcript() -> Dict[str, Any]:
    """Return a transcript that passes every built-in core check."""

    search = _good_search()
    return {
        "transcript_version": "1.0",
        "name": "example-good-provider",
        "exchanges": [
            _exchange(
                "capabilities.get",
                {},
                {"read_only": True, "mutating_operations": [], "schema_version": "1.0"},
            ),
            _exchange(
                "capabilities.read_only_probe",
                READ_ONLY_PROBE_REQUEST,
                {"state": "rejected", "code": "READ_ONLY", "side_effects": False},
            ),
            _exchange(
                "document.get",
                DOCUMENT_REQUEST,
                {
                    "state": "found",
                    "document_id": DOCUMENT_ID,
                    "content": CONTENT,
                    "media_type": "text/plain",
                    "source_hash": SOURCE_HASH,
                },
            ),
            _exchange(
                "quote.get",
                {"document_id": DOCUMENT_ID, "selector": "holding"},
                {
                    "document_id": DOCUMENT_ID,
                    "quote": SOURCE_QUOTE,
                    "span": {"start": SOURCE_START, "end": SOURCE_END, "unit": "unicode-code-point"},
                },
            ),
            _exchange("search", SEARCH_REQUEST, search),
            _exchange(
                "search.as_of",
                AS_OF_REQUEST,
                {
                    "state": "found",
                    "query": AS_OF_REQUEST["query"],
                    "as_of": AS_OF_REQUEST["as_of"],
                    "retrieved_at": "2025-01-15T12:00:00Z",
                    "results": [
                        {
                            "document_id": "doc-example-1995",
                            "effective_from": "1995-06-01",
                            "effective_to": None,
                        }
                    ],
                },
            ),
            _exchange(
                "corpus.status",
                {},
                {
                    "coverage": {
                        "jurisdictions": ["us-federal"],
                        "authority_types": ["reported-decisions"],
                        "publication_date_range": {"from": "1790-01-01", "through": "2025-01-15"},
                        "exclusions": ["sealed records", "unpublished materials not in the declared source corpus"],
                    },
                    "freshness": {
                        "snapshot_at": "2025-01-15T00:00:00Z",
                        "max_age_days": 30,
                        "status": "current",
                        "basis": "provider-declared source snapshot",
                    },
                },
            ),
            _exchange(
                "search",
                MISSING_REQUEST,
                {
                    "state": "absent",
                    "query": MISSING_REQUEST["query"],
                    "retrieved_at": "2025-01-15T12:00:00Z",
                    "results": [],
                    "absence": {
                        "code": "NO_MATCH",
                        "message": "No matching authority was found in the declared corpus.",
                    },
                },
            ),
            _exchange(
                "interpret",
                INTERPRETATION_REQUEST,
                {
                    "state": "completed",
                    "document_id": DOCUMENT_ID,
                    "segments": [
                        {
                            "kind": "source_text",
                            "text": SOURCE_QUOTE,
                            "span": {"start": SOURCE_START, "end": SOURCE_END},
                        },
                        {
                            "kind": "generated_interpretation",
                            "label": "Generated interpretation",
                            "text": "This generated summary describes the preceding source excerpt.",
                        },
                    ],
                },
            ),
            _exchange(
                "search",
                INVALID_REQUEST,
                {
                    "state": "error",
                    "error": {
                        "code": "INVALID_ARGUMENT",
                        "message": "query must be a string and limit must be non-negative",
                        "details": {"fields": ["query", "limit"]},
                    },
                },
            ),
        ],
    }


def broken_transcript() -> Dict[str, Any]:
    """Return a deliberately nonconforming transcript for demonstrations."""

    first_search = _good_search("unstable-a")
    first_search["retrieved_at"] = "yesterday"
    first_search["results"][0]["citation"] = {"canonical": "410  US  113", "display": "410  US  113"}
    first_search["results"][0]["jurisdiction"] = "federal"
    second_search = {
        "state": "found",
        "query": SEARCH_REQUEST["query"],
        "retrieved_at": "2025-01-15T12:00:00Z",
        "results": [{"document_id": "unstable-b", "score": 0.99}],
        "new_field": True,
    }
    return {
        "transcript_version": "1.0",
        "name": "example-broken-provider",
        "exchanges": [
            _exchange("capabilities.get", {}, {"read_only": False, "mutating_operations": ["create_annotation"]}),
            _exchange(
                "capabilities.read_only_probe",
                READ_ONLY_PROBE_REQUEST,
                {"state": "accepted", "code": "OK", "side_effects": True},
            ),
            _exchange(
                "document.get",
                DOCUMENT_REQUEST,
                {
                    "state": "found",
                    "document_id": DOCUMENT_ID,
                    "content": CONTENT,
                    "source_hash": "sha256:not-a-valid-digest",
                },
            ),
            _exchange(
                "quote.get",
                {"document_id": DOCUMENT_ID, "selector": "holding"},
                {
                    "document_id": DOCUMENT_ID,
                    "quote": SOURCE_QUOTE + ".",
                    "span": {"start": SOURCE_START, "end": SOURCE_END},
                },
            ),
            _exchange("search", SEARCH_REQUEST, first_search),
            _exchange("search", SEARCH_REQUEST, second_search),
            _exchange(
                "search.as_of",
                AS_OF_REQUEST,
                {
                    "state": "found",
                    "query": AS_OF_REQUEST["query"],
                    "as_of": "2010-01-01",
                    "retrieved_at": "2025-01-15T12:00:00Z",
                    "results": [{"document_id": "future-law", "effective_from": "2010-01-01", "effective_to": None}],
                },
            ),
            _exchange(
                "corpus.status",
                {},
                {
                    "coverage": {"jurisdictions": [], "authority_types": [], "exclusions": "unknown"},
                    "freshness": {"snapshot_at": "unknown", "max_age_days": -1, "status": "maybe"},
                },
            ),
            _exchange(
                "search",
                MISSING_REQUEST,
                {"state": "found", "query": MISSING_REQUEST["query"], "results": []},
            ),
            _exchange(
                "interpret",
                INTERPRETATION_REQUEST,
                {
                    "state": "completed",
                    "document_id": DOCUMENT_ID,
                    "segments": [{"kind": "answer", "text": "Source and generated text are mixed."}],
                },
            ),
            _exchange(
                "search",
                INVALID_REQUEST,
                {"state": "error", "error": {"code": "BAD_INPUT", "message": "bad", "details": {}}},
            ),
            _exchange(
                "search",
                INVALID_REQUEST,
                {"state": "error", "error": {"code": "DIFFERENT", "message": "changed", "details": {}}},
            ),
        ],
    }


def write_example(path: str, broken: bool = False, force: bool = False) -> None:
    """Write a formatted example transcript without overwriting by default."""

    destination = Path(path)
    if destination.exists() and not force:
        raise FileExistsError("refusing to overwrite existing file: {}".format(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = broken_transcript() if broken else good_transcript()
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
